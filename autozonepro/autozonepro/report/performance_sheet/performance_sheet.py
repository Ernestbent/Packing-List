import frappe
from frappe import _
import calendar

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
    columns.append({"label": _("Total of All 3"), "fieldname": "total_all_3", "fieldtype": "Int", "width": 100})
    columns.append({"label": _("Overall Daily Avg"), "fieldname": "overall_daily_avg", "fieldtype": "Float", "width": 110, "precision": 1})
    columns.append({"label": _("Total Packing"), "fieldname": "total_packing", "fieldtype": "Int", "width": 100})
    columns.append({"label": _("Total Picking"), "fieldname": "total_picking", "fieldtype": "Int", "width": 100})
    columns.append({"label": _("Total Verified"), "fieldname": "total_verified", "fieldtype": "Int", "width": 100})
    columns.append({"label": _("Total Dispatched"), "fieldname": "total_dispatched", "fieldtype": "Int", "width": 110})

    return columns

def get_data(month, year, num_days):
    # ───────── PACKING (from Packing List) ─────────
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
        AND custom_packer != ''
        AND custom_packer != 'Select'
    """, {"month": month, "year": year}, as_dict=True)

    # ───────── PICKING from Packing List ─────────
    picking_rows_packing = frappe.db.sql("""
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
        AND custom_picker != ''
        AND custom_picker != 'Select'
    """, {"month": month, "year": year}, as_dict=True)

    # ───────── PICKING from Pick List ─────────
    picking_rows_picklist = frappe.db.sql("""
    SELECT
        custom_picker AS person,
        'Picking' AS activity,
        DAY(modified) AS day_num,
        COUNT(*) AS qty
    FROM `tabPick List`
    WHERE docstatus = 1
        AND MONTH(modified) = %(month)s
        AND YEAR(modified) = %(year)s
        AND custom_picker IS NOT NULL
        AND custom_picker != ''
        AND custom_picker != 'Select'
    GROUP BY custom_picker, DAY(modified)
    """, {"month": month, "year": year}, as_dict=True)

    # ───────── VERIFY ─────────
    verifier_rows = frappe.db.sql("""
    SELECT
        modified_by AS person,
        'Verify' AS activity,
        DAY(custom_date) AS day_num,
        total_qty AS qty
    FROM `tabPacking List`
    WHERE docstatus = 1
        AND MONTH(custom_date) = %(month)s
        AND YEAR(custom_date) = %(year)s
        AND modified_by IS NOT NULL
        AND modified_by != ''
    """, {"month": month, "year": year}, as_dict=True)

    # ───────── DISPATCH (placeholder) ─────────
    dispatch_rows = []

    picking_rows = picking_rows_packing + picking_rows_picklist
    all_rows = packing_rows + picking_rows + verifier_rows + dispatch_rows

    # ───────── ALL UNIQUE PERSONS ─────────
    all_persons_result = frappe.db.sql("""
    SELECT DISTINCT custom_packer AS person
    FROM `tabPacking List`
    WHERE custom_packer IS NOT NULL AND custom_packer != '' AND custom_packer != 'Select'

    UNION

    SELECT DISTINCT custom_picker AS person
    FROM `tabPacking List`
    WHERE custom_picker IS NOT NULL AND custom_picker != '' AND custom_picker != 'Select'

    UNION

    SELECT DISTINCT custom_picker AS person
    FROM `tabPick List`
    WHERE custom_picker IS NOT NULL AND custom_picker != '' AND custom_picker != 'Select'
    """, as_dict=True)

    persons = sorted({r["person"] for r in all_persons_result if r.get("person")})

    activities = ["Packing", "Picking", "Verify", "Dispatch"]
    activity_order = {a: i for i, a in enumerate(activities)}

    # ───────── ZERO GRID ─────────
    pivot = {}
    for person in persons:
        for activity in activities:
            pivot[(person, activity)] = {
                "person": person,
                "activity": activity,
                **{f"day_{d}": 0 for d in range(1, num_days + 1)}
            }

    # ───────── FILL REAL DATA ─────────
    for row in all_rows:
        key = (row["person"], row["activity"])
        if key in pivot:
            pivot[key][f"day_{row['day_num']}"] += (row["qty"] or 0)

    # ───────── BUILD FINAL ROWS ─────────
    working_days = num_days
    data = []

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

            row["total_all_3"] = None
            row["overall_daily_avg"] = None
            row["total_packing"] = None
            row["total_picking"] = None
            row["total_verified"] = None
            row["total_dispatched"] = None

            totals_by_activity[activity] = total
            person_rows.append(row)

        # Summary on Verify row
        for row in person_rows:
            if row["activity"] == "Verify":
                t_packing = totals_by_activity.get("Packing", 0)
                t_picking = totals_by_activity.get("Picking", 0)
                t_verified = totals_by_activity.get("Verify", 0)
                t_dispatched = totals_by_activity.get("Dispatch", 0)
                total_all_3 = t_packing + t_picking + t_verified

                row["total_all_3"] = total_all_3
                row["overall_daily_avg"] = round(total_all_3 / working_days, 1) if working_days else 0
                row["total_packing"] = t_packing
                row["total_picking"] = t_picking
                row["total_verified"] = t_verified
                row["total_dispatched"] = t_dispatched
                break

        if person_rows:
            person_rows[-1]["_is_last_row"] = 1

        data.extend(person_rows)

    return data