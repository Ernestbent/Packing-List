import frappe
from frappe import _
import calendar

## Whitelist — only these display names appear in the report
ALLOWED_PERSONS = {
    "Kenneth", "Joshua", "Ali", "Maria", "Peter",
    "Owen", "Farhad", "Mehraj", "Salim", "Jawid", "Chris"
}

## Map resolved full names to preferred short display names
NAME_OVERRIDES = {
    "Nabukenya Maria": "Maria",
    "OWEN SHEN": "Owen",
}


def execute(filters=None):
    filters  = filters or {}
    month    = int(filters.get("month") or frappe.utils.getdate().month)
    year     = int(filters.get("year")  or frappe.utils.getdate().year)
    num_days = calendar.monthrange(year, month)[1]

    columns  = get_columns()
    data     = get_data(month, year, num_days)

    return columns, data


def get_columns():
    ## Fixed summary columns — no day columns needed here
    return [
        {"label": _("No."),          "fieldname": "no",          "fieldtype": "Int",   "width": 50},
        {"label": _("Name"),         "fieldname": "person",      "fieldtype": "Data",  "width": 120},
        {"label": _("Packing"),      "fieldname": "packing",     "fieldtype": "Int",   "width": 90},
        {"label": _("Picking"),      "fieldname": "picking",     "fieldtype": "Int",   "width": 90},
        {"label": _("Verify"),       "fieldname": "verified",    "fieldtype": "Int",   "width": 90},
        {"label": _("Billed"),       "fieldname": "billing",     "fieldtype": "Int",   "width": 90},
        {"label": _("Dispatched"),   "fieldname": "dispatched",  "fieldtype": "Int",   "width": 100},
        {"label": _("Total of All"), "fieldname": "total_all",   "fieldtype": "Int",   "width": 110},
        {"label": _("Daily Avg"),    "fieldname": "daily_avg",   "fieldtype": "Float", "width": 90, "precision": 1},
    ]


def get_user_name_map():
    ## Load all enabled users — email to first_name for resolving email-based owners
    users = frappe.db.sql("""
        SELECT name AS email, first_name
        FROM `tabUser`
        WHERE enabled = 1
          AND name != 'Guest'
    """, as_dict=True)
    return {u["email"].lower(): u["first_name"] for u in users}


def resolve_name(email_or_name, user_name_map):
    ## Resolve email -> first_name, then apply display-name override if defined
    if not email_or_name:
        return email_or_name
    resolved = user_name_map.get(email_or_name.lower(), email_or_name)
    return NAME_OVERRIDES.get(resolved, resolved)


def build_person_total_map(rows):
    totals = {}

    for row in rows:
        person = row["person"]
        if person not in ALLOWED_PERSONS:
            continue

        totals[person] = totals.get(person, 0) + (row["qty"] or 0)

    return totals


def get_data(month, year, num_days):
    params        = {"month": month, "year": year}
    user_name_map = get_user_name_map()
    working_days  = num_days

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

    packing_map = build_person_total_map(packing_raw)

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

    picking_map = build_person_total_map(picking_raw)

    ## VERIFY — count distinct Sales Orders verified per person for the month
    verify_raw = frappe.db.sql("""
        SELECT
            custom_verifier_2 AS person,
            COUNT(DISTINCT custom_sales_order) AS qty
        FROM `tabPacking List`
        WHERE docstatus = 1
          AND MONTH(custom_date) = %(month)s
          AND YEAR(custom_date)  = %(year)s
          AND custom_verifier_2 IS NOT NULL
          AND custom_verifier_2 NOT IN ('', 'Select')
          AND custom_sales_order IS NOT NULL
          AND custom_sales_order != ''
        GROUP BY custom_verifier_2
    """, params, as_dict=True)

    verify_map = build_person_total_map(verify_raw)

    ## BILLING — Version table: count Packed -> Billing transitions per person
    billing_raw = frappe.db.sql("""
        SELECT
            owner AS person,
            DAY(creation) AS day_num,
            COUNT(*) AS qty
        FROM `tabVersion`
        WHERE ref_doctype = 'Sales Order'
          AND MONTH(creation) = %(month)s
          AND YEAR(creation)  = %(year)s
          AND data LIKE '%%"workflow_state"%%Packed%%Billing%%'
        GROUP BY owner, DAY(creation)
    """, params, as_dict=True)

    billing_rows = [{"person": resolve_name(r["person"], user_name_map),
                     "activity": "Billing", "day_num": r["day_num"],
                     "qty": r["qty"]} for r in billing_raw]

    billing_map = build_person_total_map(billing_rows)

    ## DISPATCH — Version table: count In Transit -> Dispatched transitions per person
    dispatch_raw = frappe.db.sql("""
        SELECT
            owner AS person,
            DAY(creation) AS day_num,
            COUNT(*) AS qty
        FROM `tabVersion`
        WHERE ref_doctype = 'Sales Order'
          AND MONTH(creation) = %(month)s
          AND YEAR(creation)  = %(year)s
          AND data LIKE '%%"workflow_state"%%In Transit%%Dispatched%%'
        GROUP BY owner, DAY(creation)
    """, params, as_dict=True)

    dispatch_rows = [{"person": resolve_name(r["person"], user_name_map),
                      "activity": "Dispatch", "day_num": r["day_num"],
                      "qty": r["qty"]} for r in dispatch_raw]

    dispatch_map = build_person_total_map(dispatch_rows)

    ## Build one summary row per allowed person, sorted alphabetically
    data = []
    for idx, person in enumerate(sorted(ALLOWED_PERSONS), start=1):
        t_packing    = packing_map.get(person, 0)  or 0
        t_picking    = picking_map.get(person, 0)  or 0
        t_verified   = verify_map.get(person, 0)   or 0
        t_billing    = billing_map.get(person, 0)  or 0
        t_dispatched = dispatch_map.get(person, 0) or 0

        ## Total of All = Packing + Picking + Verify + Billing (matches main report)
        total_all  = t_packing + t_picking + t_verified + t_billing
        daily_avg  = round(total_all / working_days, 1) if working_days else 0

        data.append({
            "no":         idx,
            "person":     person,
            "packing":    t_packing,
            "picking":    t_picking,
            "verified":   t_verified,
            "billing":    t_billing,
            "dispatched": t_dispatched,
            "total_all":  total_all,
            "daily_avg":  daily_avg,
            "_is_summary": 1,                    ## flag used by JS formatter for styling
        })

    return data
