import frappe
from frappe import _
import calendar

## Only these people should appear in the report — filter out everyone else
ALLOWED_PERSONS = {
    "Kenneth", "Joshua", "Ali", "Maria", "Peter",
    "Owen", "Farhad", "Mehraj", "Salim", "Jawid", "Chris"
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
    ## Resolve email to first_name if found, otherwise return value as-is
    if not email_or_name:
        return email_or_name
    return user_name_map.get(email_or_name.lower(), email_or_name)

def get_data(month, year, num_days):
    params = {"month": month, "year": year}

    ## Load user map once for all email resolution below
    user_name_map = get_user_name_map()

    ## PACKING: custom_packer and custom_date on Packing List
    packing_rows = frappe.db.sql("""
        SELECT
            custom_packer AS person,
            'Packing' AS activity,
            DAY(custom_date) AS day_num,
            total_qty AS qty
        FROM `tabPacking List`
        WHERE docstatus = 1
            AND MONTH(custom_date) = %(month)s
            AND YEAR(custom_date) = %(year)s
            AND custom_packer IS NOT NULL
            AND custom_packer NOT IN ('', 'Select')
    """, params, as_dict=True)

    ## PICKING: custom_picker fetched from Pick List via Packing List
    picking_rows = frappe.db.sql("""
        SELECT
            custom_picker AS person,
            'Picking' AS activity,
            DAY(custom_date) AS day_num,
            total_qty AS qty
        FROM `tabPacking List`
        WHERE docstatus = 1
            AND MONTH(custom_date) = %(month)s
            AND YEAR(custom_date) = %(year)s
            AND custom_picker IS NOT NULL
            AND custom_picker NOT IN ('', 'Select')
    """, params, as_dict=True)

    ## VERIFY: custom_verifier_2 on Packing List
    verifier_rows = frappe.db.sql("""
        SELECT
            custom_verifier_2 AS person,
            'Verify' AS activity,
            DAY(custom_date) AS day_num,
            total_qty AS qty
        FROM `tabPacking List`
        WHERE docstatus = 1
            AND MONTH(custom_date) = %(month)s
            AND YEAR(custom_date) = %(year)s
            AND custom_verifier_2 IS NOT NULL
            AND custom_verifier_2 NOT IN ('', 'Select')
    """, params, as_dict=True)

    ## BILLING: owner is email — resolved to first_name
    billing_rows = frappe.db.sql("""
        SELECT
            owner AS person,
            'Billing' AS activity,
            DAY(posting_date) AS day_num,
            COUNT(*) AS qty
        FROM `tabSales Invoice`
        WHERE docstatus = 1
            AND MONTH(posting_date) = %(month)s
            AND YEAR(posting_date) = %(year)s
            AND owner IS NOT NULL
            AND owner != ''
        GROUP BY owner, DAY(posting_date)
    """, params, as_dict=True)

    ## Resolve billing owner emails to first_name
    for r in billing_rows:
        r["person"] = resolve_name(r["person"], user_name_map)

    ## DISPATCH: Version table workflow transition from In Transit to Dispatched
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

    ## Resolve dispatch owner emails to first_name
    dispatch_rows = []
    for r in dispatch_rows_raw:
        dispatch_rows.append({
            "person": resolve_name(r["person"], user_name_map),
            "activity": "Dispatch",
            "day_num": r["day_num"],
            "qty": r["qty"]
        })

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

            ## Clear summary columns — filled on last row below
            row["total_all_4"] = None
            row["overall_daily_avg"] = None
            row["total_packing"] = None
            row["total_picking"] = None
            row["total_verified"] = None
            row["total_billing"] = None
            row["total_dispatched"] = None

            totals_by_activity[activity] = total
            person_rows.append(row)

        ## Summary always on last row per person
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
            last["total_packing"] = t_packing
            last["total_picking"] = t_picking
            last["total_verified"] = t_verified
            last["total_billing"] = t_billing
            last["total_dispatched"] = t_dispatched

        data.extend(person_rows)

    return data