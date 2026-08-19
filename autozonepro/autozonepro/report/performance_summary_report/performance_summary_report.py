import frappe
from frappe import _
import calendar

## Whitelist — only these display names appear in the report
ALLOWED_PERSONS = {
    "Kenneth", "Joshua", "Ali", "Maria", "Peter", "Arthur", "Jovan",
    "Owen", "Farhad", "Mehraj", "Salim", "Jawid", "Chris",
    "George", "Osbert", "Moses", "Charles"
}

PERSON_EMAILS = {
    "nduggaarthur@gmail.com": "Arthur",
    "muwanguzijovan34@gmail.com": "Jovan",
}

JUNE_ONWARD_EXCLUDED_PERSONS = {"Chris", "Owen"}
JULY_2026_ONWARD_EXCLUDED_PERSONS = {"Osbert", "Peter"}
MAY_ONWARD_PERSONS = {"George", "Osbert"}

## Name overrides — genuine typos or full name mappings that title() alone cannot fix
NAME_OVERRIDES = {
    "Nabukenya Maria": "Maria",
    "OWEN SHEN":       "Owen",
    "Farhard":         "Farhad",
}


def execute(filters=None):
    filters  = filters or {}
    month    = int(filters.get("month") or frappe.utils.getdate().month)
    year     = int(filters.get("year")  or frappe.utils.getdate().year)
    num_days = calendar.monthrange(year, month)[1]

    columns = get_columns(month, year)
    data    = get_data(month, year, num_days)

    return columns, data


def get_previous_months(month, year, count=3):
    months = []
    for offset in range(1, count + 1):
        prev_month = month - offset
        prev_year = year
        while prev_month < 1:
            prev_month += 12
            prev_year -= 1
        months.append((prev_month, prev_year))
    return months


def get_columns(month, year):
    ## Fixed summary columns — counts are distinct Sales Orders; picked qty is item quantity.
    columns = [
        {"label": _("No."),              "fieldname": "no",              "fieldtype": "Int",   "width": 50},
        {"label": _("Name"),             "fieldname": "person",          "fieldtype": "Data",  "width": 120},
        {"label": _("Packing"),          "fieldname": "packing",         "fieldtype": "Int",   "width": 90},
        {"label": _("Picking"),          "fieldname": "picking",         "fieldtype": "Int",   "width": 90},
        {"label": _("Verify"),           "fieldname": "verified",        "fieldtype": "Int",   "width": 90},
        {"label": _("Billed"),           "fieldname": "billing",         "fieldtype": "Int",   "width": 90},
        {"label": _("Dispatched"),       "fieldname": "dispatched",      "fieldtype": "Int",   "width": 100},
        {"label": _("Total of All"),     "fieldname": "total_all",       "fieldtype": "Int",   "width": 110},
        {"label": _("Daily Avg"),        "fieldname": "daily_avg",       "fieldtype": "Float", "width": 90, "precision": 1},
        {"label": _("Qty Picked"),       "fieldname": "qty_picked",      "fieldtype": "Int",   "width": 100},
        {"label": _("Total Amount"),     "fieldname": "so_amount",       "fieldtype": "Currency", "width": 130, "precision": 0},
    ]

    for idx, (prev_month, prev_year) in enumerate(get_previous_months(month, year), start=1):
        columns.append({
            "label": _(f"{calendar.month_abbr[prev_month]} {prev_year}"),
            "fieldname": f"previous_month_{idx}",
            "fieldtype": "Int",
            "width": 95,
        })

    return columns


def get_user_name_map():
    ## Load all enabled users — email to first_name for resolving email-based owners
    users = frappe.db.sql("""
        SELECT name AS email, first_name
        FROM `tabUser`
        WHERE enabled = 1
          AND name != 'Guest'
    """, as_dict=True)
    user_name_map = {u["email"].lower(): u["first_name"] for u in users}
    user_name_map.update(PERSON_EMAILS)
    return user_name_map


def resolve_name(email_or_name, user_name_map):
    if not email_or_name:
        return email_or_name

    ## Step 1: resolve email to first_name via user_map
    resolved = user_name_map.get(email_or_name.lower(), email_or_name)

    ## Step 2: apply override for known typos or full name corrections
    cleaned = NAME_OVERRIDES.get(resolved, resolved)

    ## Step 3: strip and title-case as final safety net
    return cleaned.strip().title()


def get_allowed_persons(month, year):
    persons = set(ALLOWED_PERSONS)
    if month < 5:
        persons -= MAY_ONWARD_PERSONS
    if month >= 6:
        persons -= JUNE_ONWARD_EXCLUDED_PERSONS
    if (year, month) >= (2026, 7):
        persons -= JULY_2026_ONWARD_EXCLUDED_PERSONS
    return persons


def build_person_total_map(rows):
    ## Sum qty per person — only allowed persons are counted
    totals = {}
    for row in rows:
        person = row["person"]
        if person not in ALLOWED_PERSONS:
            continue
        totals[person] = totals.get(person, 0) + (row["qty"] or 0)
    return totals


def get_month_performance_totals(month, year, user_name_map):
    params = {"month": month, "year": year}

    packing_raw = frappe.db.sql("""
        SELECT custom_packer AS person, COUNT(DISTINCT custom_sales_order) AS qty
        FROM `tabPacking List`
        WHERE docstatus = 1
          AND MONTH(custom_date) = %(month)s
          AND YEAR(custom_date)  = %(year)s
          AND custom_packer IS NOT NULL
          AND custom_packer NOT IN ('', 'Select')
          AND custom_sales_order IS NOT NULL
          AND custom_sales_order != ''
        GROUP BY custom_packer
    """, params, as_dict=True)

    picking_raw = frappe.db.sql("""
        SELECT custom_picker AS person, COUNT(DISTINCT custom_sales_order) AS qty
        FROM `tabPacking List`
        WHERE docstatus = 1
          AND MONTH(custom_date) = %(month)s
          AND YEAR(custom_date)  = %(year)s
          AND custom_picker IS NOT NULL
          AND custom_picker NOT IN ('', 'Select')
          AND custom_sales_order IS NOT NULL
          AND custom_sales_order != ''
        GROUP BY custom_picker
    """, params, as_dict=True)

    verify_raw = frappe.db.sql("""
        SELECT person, custom_sales_order
        FROM (
            SELECT owner AS person, custom_sales_order
            FROM `tabPacking List`
            WHERE docstatus = 1
              AND MONTH(custom_date) = %(month)s
              AND YEAR(custom_date)  = %(year)s
              AND custom_sales_order IS NOT NULL
              AND custom_sales_order != ''

            UNION ALL

            SELECT custom_verifier_2 AS person, custom_sales_order
            FROM `tabPacking List`
            WHERE docstatus = 1
              AND MONTH(custom_date) = %(month)s
              AND YEAR(custom_date)  = %(year)s
              AND custom_verifier_2 IS NOT NULL
              AND custom_verifier_2 NOT IN ('', 'Select')
              AND custom_sales_order IS NOT NULL
              AND custom_sales_order != ''
        ) combined
    """, params, as_dict=True)

    seen = set()
    verify_counts = {}
    for r in verify_raw:
        name = resolve_name(r["person"], user_name_map)
        dedup_key = (name, r["custom_sales_order"])
        if dedup_key in seen:
            continue
        seen.add(dedup_key)
        verify_counts[name] = verify_counts.get(name, 0) + 1

    billing_raw = frappe.db.sql("""
        SELECT owner AS person, COUNT(*) AS qty
        FROM `tabVersion`
        WHERE ref_doctype = 'Sales Order'
          AND MONTH(creation) = %(month)s
          AND YEAR(creation)  = %(year)s
          AND data LIKE '%%"workflow_state"%%Packed%%Billing%%'
        GROUP BY owner
    """, params, as_dict=True)

    dispatch_raw = frappe.db.sql("""
        SELECT owner AS person, COUNT(*) AS qty
        FROM `tabVersion`
        WHERE ref_doctype = 'Sales Order'
          AND MONTH(creation) = %(month)s
          AND YEAR(creation)  = %(year)s
          AND data LIKE '%%"workflow_state"%%In Transit%%Dispatched%%'
        GROUP BY owner
    """, params, as_dict=True)

    total_map = {}
    rows = []
    rows.extend({"person": resolve_name(r["person"], user_name_map), "qty": r["qty"]} for r in packing_raw)
    rows.extend({"person": resolve_name(r["person"], user_name_map), "qty": r["qty"]} for r in picking_raw)
    rows.extend({"person": person, "qty": qty} for person, qty in verify_counts.items())
    rows.extend({"person": resolve_name(r["person"], user_name_map), "qty": r["qty"]} for r in billing_raw)
    rows.extend({"person": resolve_name(r["person"], user_name_map), "qty": r["qty"]} for r in dispatch_raw)

    for person, total in build_person_total_map(rows).items():
        total_map[person] = total

    return total_map


def get_data(month, year, num_days):
    params        = {"month": month, "year": year}
    user_name_map = get_user_name_map()
    allowed_persons = get_allowed_persons(month, year)
    working_days  = num_days
    previous_month_totals = [
        get_month_performance_totals(prev_month, prev_year, user_name_map)
        for prev_month, prev_year in get_previous_months(month, year)
    ]

    ## PACKING — count distinct Sales Orders packed per person for the month
    packing_raw = frappe.db.sql("""
        SELECT
            custom_packer AS person,
            COUNT(DISTINCT custom_sales_order) AS qty
        FROM `tabPacking List`
        WHERE docstatus = 1
          AND MONTH(custom_date) = %(month)s
          AND YEAR(custom_date)  = %(year)s
          AND custom_packer IS NOT NULL
          AND custom_packer NOT IN ('', 'Select')
          AND custom_sales_order IS NOT NULL
          AND custom_sales_order != ''
        GROUP BY custom_packer
    """, params, as_dict=True)

    ## Resolve names and merge — total_packing = same SO count as packing column
    packing_merged = {}
    for r in packing_raw:
        name = resolve_name(r["person"], user_name_map)
        packing_merged[name] = packing_merged.get(name, 0) + (r["qty"] or 0)

    packing_map = build_person_total_map(
        [{"person": k, "qty": v} for k, v in packing_merged.items()]
    )

    ## PICKING — count distinct Sales Orders picked per person for the month
    picking_raw = frappe.db.sql("""
        SELECT
            custom_picker AS person,
            COUNT(DISTINCT custom_sales_order) AS qty
        FROM `tabPacking List`
        WHERE docstatus = 1
          AND MONTH(custom_date) = %(month)s
          AND YEAR(custom_date)  = %(year)s
          AND custom_picker IS NOT NULL
          AND custom_picker NOT IN ('', 'Select')
          AND custom_sales_order IS NOT NULL
          AND custom_sales_order != ''
        GROUP BY custom_picker
    """, params, as_dict=True)

    ## Resolve names and merge — total_picking = same SO count as picking column
    picking_merged = {}
    for r in picking_raw:
        name = resolve_name(r["person"], user_name_map)
        picking_merged[name] = picking_merged.get(name, 0) + (r["qty"] or 0)

    picking_map = build_person_total_map(
        [{"person": k, "qty": v} for k, v in picking_merged.items()]
    )

    ## PICKED QUANTITY — sum picked item quantities per picker for the month
    picked_qty_raw = frappe.db.sql("""
        SELECT
            pl.custom_picker AS person,
            SUM(COALESCE(pli.qty, 0)) AS qty
        FROM `tabPacking List` pl
        INNER JOIN `tabItems` pli
            ON pli.parent = pl.name
            AND pli.parenttype = 'Packing List'
            AND pli.parentfield = 'table_ttya'
        WHERE pl.docstatus = 1
          AND MONTH(pl.custom_date) = %(month)s
          AND YEAR(pl.custom_date)  = %(year)s
          AND pl.custom_picker IS NOT NULL
          AND pl.custom_picker NOT IN ('', 'Select')
          AND pl.custom_sales_order IS NOT NULL
          AND pl.custom_sales_order != ''
        GROUP BY pl.custom_picker
    """, params, as_dict=True)

    ## Resolve names and merge — qty_picked is item quantity, separate from SO counts
    picked_qty_merged = {}
    for r in picked_qty_raw:
        name = resolve_name(r["person"], user_name_map)
        picked_qty_merged[name] = picked_qty_merged.get(name, 0) + (r["qty"] or 0)

    picked_qty_map = build_person_total_map(
        [{"person": k, "qty": v} for k, v in picked_qty_merged.items()]
    )

    ## PICKED SALES ORDER AMOUNT — picked item qty x Sales Order Item net rate.
    ## This avoids counting SO lines that were not actually picked.
    picked_so_amount_raw = frappe.db.sql("""
        SELECT
            pl.custom_picker AS person,
            SUM(COALESCE(pli.qty, 0) * COALESCE(soi.net_rate, 0)) AS qty
        FROM `tabPacking List` pl
        INNER JOIN `tabItems` pli
            ON pli.parent = pl.name
            AND pli.parenttype = 'Packing List'
            AND pli.parentfield = 'table_ttya'
        LEFT JOIN (
            SELECT
                parent,
                item_code,
                CASE
                    WHEN SUM(qty) != 0 THEN SUM(net_amount) / SUM(qty)
                    ELSE MAX(net_rate)
                END AS net_rate
            FROM `tabSales Order Item`
            GROUP BY parent, item_code
        ) soi
            ON soi.parent = pl.custom_sales_order
            AND soi.item_code = pli.item
        WHERE pl.docstatus = 1
          AND MONTH(pl.custom_date) = %(month)s
          AND YEAR(pl.custom_date)  = %(year)s
          AND pl.custom_picker IS NOT NULL
          AND pl.custom_picker NOT IN ('', 'Select')
          AND pl.custom_sales_order IS NOT NULL
          AND pl.custom_sales_order != ''
        GROUP BY pl.custom_picker
    """, params, as_dict=True)

    ## Resolve names and merge — amount is separate from SO/action counts
    picked_so_amount_merged = {}
    for r in picked_so_amount_raw:
        name = resolve_name(r["person"], user_name_map)
        picked_so_amount_merged[name] = picked_so_amount_merged.get(name, 0) + (r["qty"] or 0)

    picked_so_amount_map = build_person_total_map(
        [{"person": k, "qty": v} for k, v in picked_so_amount_merged.items()]
    )

    ## VERIFY — Verifier 1 = owner who submitted, Verifier 2 = custom_verifier_2
    ## Deduplicated by (resolved_name, sales_order) to avoid double counting V1 == V2
    verify_raw = frappe.db.sql("""
        SELECT person, custom_sales_order
        FROM (
            -- Verifier 1: the person who submitted the Packing List
            SELECT owner AS person, custom_sales_order
            FROM `tabPacking List`
            WHERE docstatus = 1
              AND MONTH(custom_date) = %(month)s
              AND YEAR(custom_date)  = %(year)s
              AND custom_sales_order IS NOT NULL
              AND custom_sales_order != ''

            UNION ALL

            -- Verifier 2: explicitly selected on the form
            SELECT custom_verifier_2 AS person, custom_sales_order
            FROM `tabPacking List`
            WHERE docstatus = 1
              AND MONTH(custom_date) = %(month)s
              AND YEAR(custom_date)  = %(year)s
              AND custom_verifier_2 IS NOT NULL
              AND custom_verifier_2 NOT IN ('', 'Select')
              AND custom_sales_order IS NOT NULL
              AND custom_sales_order != ''
        ) combined
    """, params, as_dict=True)

    ## Deduplicate in Python — skip if same person already counted for this SO
    seen          = set()
    verify_counts = {}
    for r in verify_raw:
        name      = resolve_name(r["person"], user_name_map)
        so        = r["custom_sales_order"]
        dedup_key = (name, so)
        if dedup_key in seen:
            continue
        seen.add(dedup_key)
        verify_counts[name] = verify_counts.get(name, 0) + 1

    verify_map = build_person_total_map(
        [{"person": k, "qty": v} for k, v in verify_counts.items()]
    )

    ## BILLING — Version table: count Packed -> Billing transitions per person
    billing_raw = frappe.db.sql("""
        SELECT
            owner AS person,
            COUNT(*) AS qty
        FROM `tabVersion`
        WHERE ref_doctype = 'Sales Order'
          AND MONTH(creation) = %(month)s
          AND YEAR(creation)  = %(year)s
          AND data LIKE '%%"workflow_state"%%Packed%%Billing%%'
        GROUP BY owner
    """, params, as_dict=True)

    billing_map = build_person_total_map(
        [{"person": resolve_name(r["person"], user_name_map), "qty": r["qty"]}
         for r in billing_raw]
    )

    ## DISPATCH — Version table: count In Transit -> Dispatched transitions per person
    dispatch_raw = frappe.db.sql("""
        SELECT
            owner AS person,
            COUNT(*) AS qty
        FROM `tabVersion`
        WHERE ref_doctype = 'Sales Order'
          AND MONTH(creation) = %(month)s
          AND YEAR(creation)  = %(year)s
          AND data LIKE '%%"workflow_state"%%In Transit%%Dispatched%%'
        GROUP BY owner
    """, params, as_dict=True)

    dispatch_map = build_person_total_map(
        [{"person": resolve_name(r["person"], user_name_map), "qty": r["qty"]}
         for r in dispatch_raw]
    )

    ## Build one summary row per allowed person sorted alphabetically
    data = []
    for idx, person in enumerate(sorted(allowed_persons), start=1):
        t_packing    = packing_map.get(person, 0)  or 0
        t_picking    = picking_map.get(person, 0)  or 0
        t_qty_picked = int(picked_qty_map.get(person, 0) or 0)
        t_so_amount  = int(round(picked_so_amount_map.get(person, 0) or 0))
        t_verified   = verify_map.get(person, 0)   or 0
        t_billing    = billing_map.get(person, 0)  or 0
        t_dispatched = dispatch_map.get(person, 0) or 0

        ## Total of All = Packing + Picking + Verify + Billing + Dispatched
        total_all = t_packing + t_picking + t_verified + t_billing + t_dispatched
        daily_avg = round(total_all / working_days, 1) if working_days else 0

        data.append({
            "no":          idx,
            "person":      person,
            "packing":     t_packing,
            "picking":     t_picking,
            "qty_picked":  t_qty_picked,
            "so_amount":   t_so_amount,
            "verified":    t_verified,
            "billing":     t_billing,
            "dispatched":  t_dispatched,
            "total_all":   total_all,
            "daily_avg":   daily_avg,
            **{
                f"previous_month_{prev_idx}": int(month_totals.get(person, 0) or 0)
                for prev_idx, month_totals in enumerate(previous_month_totals, start=1)
            },
            ## Total columns mirror the SO counts above — consistent with main columns
            "total_packing":    t_packing,
            "total_picking":    t_picking,
            "total_qty_picked": t_qty_picked,
            "total_so_amount":  t_so_amount,
            "total_verified":   t_verified,
            "total_billing":    t_billing,
            "total_dispatched": t_dispatched,
            "_is_summary": 1,
        })

    return data
