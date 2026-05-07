import frappe
from frappe import _
import calendar

## Only these people should appear in the report — filter out everyone else
ALLOWED_PERSONS = {
    "Kenneth", "Joshua", "Ali", "Maria", "Peter",
    "Owen", "Farhad", "Mehraj", "Salim", "Jawid", "Chris"
}

## Name overrides — map resolved full names to preferred display names
NAME_OVERRIDES = {
    "Nabukenya Maria": "Maria",
    "OWEN SHEN": "Owen",
}

def execute(filters=None):
    filters = filters or {}
    month = int(filters.get("month") or frappe.utils.getdate().month)
    year = int(filters.get("year") or frappe.utils.getdate().year)
    num_days = calendar.monthrange(year, month)[1]

    columns = get_columns(num_days)
    data = get_data(month, year, num_days)

    return columns, data

def get_columns(num_days):
    columns = [
        {"label": _("Employee Name"), "fieldname": "person", "fieldtype": "Data", "width": 140},
        {"label": _("Activity"), "fieldname": "activity", "fieldtype": "Data", "width": 110},
    ]

    for day in range(1, num_days + 1):
        columns.append({
            "label": str(day),
            "fieldname": f"day_{day}",
            "fieldtype": "Int",
            "width": 38
        })

    columns.append({"label": _("Total"), "fieldname": "total", "fieldtype": "Int", "width": 65})
    columns.append({"label": _("Daily Avg"), "fieldname": "daily_avg", "fieldtype": "Float", "width": 75, "precision": 1})
    columns.append({"label": _("Total of All 4"), "fieldname": "total_all_4", "fieldtype": "Int", "width": 100})
    columns.append({"label": _("Overall Daily Avg"), "fieldname": "overall_daily_avg", "fieldtype": "Float", "width": 110, "precision": 1})
    columns.append({"label": _("Total Packing"), "fieldname": "total_packing", "fieldtype": "Int", "width": 100})
    columns.append({"label": _("Total Picking"), "fieldname": "total_picking", "fieldtype": "Int", "width": 100})
    columns.append({"label": _("Total Verified"), "fieldname": "total_verified", "fieldtype": "Int", "width": 100})
    columns.append({"label": _("Total Billing"), "fieldname": "total_billing", "fieldtype": "Int", "width": 100})
    columns.append({"label": _("Total Dispatched"), "fieldname": "total_dispatched", "fieldtype": "Int", "width": 110})

    return columns

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
    ## Resolve email to first_name, then apply override if needed
    if not email_or_name:
        return email_or_name
    resolved = user_name_map.get(email_or_name.lower(), email_or_name)
    return NAME_OVERRIDES.get(resolved, resolved)

def get_data(month, year, num_days):
    params = {"month": month, "year": year}

    ## Load user map once for all email resolution below
    user_name_map = get_user_name_map()

    ## PACKING ORDERS: count of distinct Sales Orders packed per person per day
    packing_orders_raw = frappe.db.sql("""
        SELECT
            custom_packer AS person,
            DAY(custom_date) AS day_num,
            COUNT(DISTINCT custom_sales_order) AS qty
        FROM `tabPacking List`
        WHERE docstatus = 1
            AND MONTH(custom_date) = %(month)s
            AND YEAR(custom_date) = %(year)s
            AND custom_packer IS NOT NULL
            AND custom_packer NOT IN ('', 'Select')
            AND custom_sales_order IS NOT NULL
            AND custom_sales_order != ''
        GROUP BY custom_packer, DAY(custom_date)
    """, params, as_dict=True)

    packing_rows = [{"person": r["person"], "activity": "Packing",
                     "day_num": r["day_num"], "qty": r["qty"]} for r in packing_orders_raw]

    ## PACKING QTY: total_qty per person for Total Packing summary column
    packing_qty_raw = frappe.db.sql("""
        SELECT
            custom_packer AS person,
            SUM(total_qty) AS total_qty
        FROM `tabPacking List`
        WHERE docstatus = 1
            AND MONTH(custom_date) = %(month)s
            AND YEAR(custom_date) = %(year)s
            AND custom_packer IS NOT NULL
            AND custom_packer NOT IN ('', 'Select')
        GROUP BY custom_packer
    """, params, as_dict=True)

    packing_qty_map = {r["person"]: r["total_qty"] for r in packing_qty_raw}

    ## PICKING ORDERS: count of distinct Sales Orders picked per person per day
    picking_orders_raw = frappe.db.sql("""
        SELECT
            custom_picker AS person,
            DAY(custom_date) AS day_num,
            COUNT(DISTINCT custom_sales_order) AS qty
        FROM `tabPacking List`
        WHERE docstatus = 1
            AND MONTH(custom_date) = %(month)s
            AND YEAR(custom_date) = %(year)s
            AND custom_picker IS NOT NULL
            AND custom_picker NOT IN ('', 'Select')
            AND custom_sales_order IS NOT NULL
            AND custom_sales_order != ''
        GROUP BY custom_picker, DAY(custom_date)
    """, params, as_dict=True)

    picking_rows = [{"person": r["person"], "activity": "Picking",
                     "day_num": r["day_num"], "qty": r["qty"]} for r in picking_orders_raw]

    ## PICKING QTY: total_qty per person for Total Picking summary column
    picking_qty_raw = frappe.db.sql("""
        SELECT
            custom_picker AS person,
            SUM(total_qty) AS total_qty
        FROM `tabPacking List`
        WHERE docstatus = 1
            AND MONTH(custom_date) = %(month)s
            AND YEAR(custom_date) = %(year)s
            AND custom_picker IS NOT NULL
            AND custom_picker NOT IN ('', 'Select')
        GROUP BY custom_picker
    """, params, as_dict=True)

    picking_qty_map = {r["person"]: r["total_qty"] for r in picking_qty_raw}

    ## VERIFY ORDERS: count of distinct Sales Orders verified per person per day
    verifier_orders_raw = frappe.db.sql("""
        SELECT
            custom_verifier_2 AS person,
            DAY(custom_date) AS day_num,
            COUNT(DISTINCT custom_sales_order) AS qty
        FROM `tabPacking List`
        WHERE docstatus = 1
            AND MONTH(custom_date) = %(month)s
            AND YEAR(custom_date) = %(year)s
            AND custom_verifier_2 IS NOT NULL
            AND custom_verifier_2 NOT IN ('', 'Select')
            AND custom_sales_order IS NOT NULL
            AND custom_sales_order != ''
        GROUP BY custom_verifier_2, DAY(custom_date)
    """, params, as_dict=True)

    verifier_rows = [{"person": r["person"], "activity": "Verify",
                      "day_num": r["day_num"], "qty": r["qty"]} for r in verifier_orders_raw]

    ## VERIFY QTY: total_qty per person for Total Verified summary column
    verifier_qty_raw = frappe.db.sql("""
        SELECT
            custom_verifier_2 AS person,
            SUM(total_qty) AS total_qty
        FROM `tabPacking List`
        WHERE docstatus = 1
            AND MONTH(custom_date) = %(month)s
            AND YEAR(custom_date) = %(year)s
            AND custom_verifier_2 IS NOT NULL
            AND custom_verifier_2 NOT IN ('', 'Select')
        GROUP BY custom_verifier_2
    """, params, as_dict=True)

    verifier_qty_map = {r["person"]: r["total_qty"] for r in verifier_qty_raw}

    ## BILLING: Version table — who changed workflow state from Packed to Billing
    billing_rows_raw = frappe.db.sql("""
        SELECT
            owner AS person,
            DAY(creation) AS day_num,
            COUNT(*) AS qty
        FROM `tabVersion`
        WHERE ref_doctype = 'Sales Order'
            AND MONTH(creation) = %(month)s
            AND YEAR(creation) = %(year)s
            AND data LIKE '%%"workflow_state"%%Packed%%Billing%%'
        GROUP BY owner, DAY(creation)
    """, params, as_dict=True)

    billing_rows = [{"person": resolve_name(r["person"], user_name_map),
                     "activity": "Billing", "day_num": r["day_num"],
                     "qty": r["qty"]} for r in billing_rows_raw]

    ## DISPATCH: Version table — who changed workflow from In Transit to Dispatched
    dispatch_rows_raw = frappe.db.sql("""
        SELECT
            owner AS person,
            DAY(creation) AS day_num,
            COUNT(*) AS qty
        FROM `tabVersion`
        WHERE ref_doctype = 'Sales Order'
            AND MONTH(creation) = %(month)s
            AND YEAR(creation) = %(year)s
            AND data LIKE '%%"workflow_state"%%In Transit%%Dispatched%%'
        GROUP BY owner, DAY(creation)
    """, params, as_dict=True)

    dispatch_rows = [{"person": resolve_name(r["person"], user_name_map),
                      "activity": "Dispatch", "day_num": r["day_num"],
                      "qty": r["qty"]} for r in dispatch_rows_raw]

    all_rows = packing_rows + picking_rows + verifier_rows + billing_rows + dispatch_rows

    ## Use fixed ALLOWED_PERSONS as the person list — ignore anyone not in the whitelist
    persons = sorted(ALLOWED_PERSONS)

    activities = ["Packing", "Picking", "Verify", "Billing", "Dispatch"]
    activity_order = {a: i for i, a in enumerate(activities)}

    ## Build empty pivot grid for every allowed person x activity
    pivot = {}
    for person in persons:
        for activity in activities:
            pivot[(person, activity)] = {
                "person": person,
                "activity": activity,
                **{f"day_{d}": 0 for d in range(1, num_days + 1)}
            }

    ## Fill real data — rows for persons not in ALLOWED_PERSONS are silently skipped
    for row in all_rows:
        key = (row["person"], row["activity"])
        if key in pivot:
            pivot[key][f"day_{row['day_num']}"] += (row["qty"] or 0)

    working_days = num_days
    data = []

    ## Group pivot keys by person sorted by activity order
    persons_keys = {}
    for key in sorted(pivot.keys(), key=lambda k: (k[0], activity_order.get(k[1], 99))):
        person = key[0]
        if person not in persons_keys:
            persons_keys[person] = []
        persons_keys[person].append(key)

    for person, keys in persons_keys.items():
        totals_by_activity = {}
        person_rows = []

        for i, key in enumerate(keys):
            row = pivot[key]
            activity = key[1]

            total = sum(row[f"day_{d}"] for d in range(1, num_days + 1))
            row["total"] = total
            row["daily_avg"] = round(total / working_days, 1) if working_days else 0
            row["person"] = person if i == 0 else ""
            row["_is_first_row"] = 1 if i == 0 else 0
            row["_is_last_row"] = 0

            ## Each summary column shows on its own activity row — None on others
            row["total_packing"] = (packing_qty_map.get(person, 0) or 0) if activity == "Packing" else None
            row["total_picking"] = (picking_qty_map.get(person, 0) or 0) if activity == "Picking" else None
            row["total_verified"] = (verifier_qty_map.get(person, 0) or 0) if activity == "Verify" else None
            row["total_billing"] = total if activity == "Billing" else None
            row["total_dispatched"] = total if activity == "Dispatch" else None

            ## Combined summary cleared here — filled on last row below
            row["total_all_4"] = None
            row["overall_daily_avg"] = None

            totals_by_activity[activity] = total
            person_rows.append(row)

        ## Combined summary always on last row per person
        if person_rows:
            t_packing = totals_by_activity.get("Packing", 0)
            t_picking = totals_by_activity.get("Picking", 0)
            t_verified = totals_by_activity.get("Verify", 0)
            t_billing = totals_by_activity.get("Billing", 0)
            t_dispatched = totals_by_activity.get("Dispatch", 0)
            total_all_4 = t_packing + t_picking + t_verified + t_billing

            last = person_rows[-1]
            last["_is_last_row"] = 1
            last["total_all_4"] = total_all_4
            last["overall_daily_avg"] = round(total_all_4 / working_days, 1) if working_days else 0

        data.extend(person_rows)

    return data