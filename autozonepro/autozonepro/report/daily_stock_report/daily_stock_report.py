import frappe
from frappe import _
import calendar
from datetime import date


def execute(filters=None):
    filters = frappe._dict(filters or {})

    if not filters.month or not filters.year:
        frappe.throw(_("Please select Month and Year"))

    columns = get_columns(filters)
    data = get_data(filters)
    return columns, data


def get_columns(filters):
    month = int(filters.month)
    year = int(filters.year)
    days_in_month = calendar.monthrange(year, month)[1]

    columns = [
        {
            "label": _("Item Code"),
            "fieldname": "item_code",
            "fieldtype": "Link",
            "options": "Item",
            "width": 180
        },
        {
            "label": _("Warehouse"),
            "fieldname": "warehouse",
            "fieldtype": "Link",
            "options": "Warehouse",
            "width": 180
        },
    ]

    ## Add one column per day in the selected month
    for day in range(1, days_in_month + 1):
        columns.append({
            "label": str(day),
            "fieldname": "day_{}".format(day),
            "fieldtype": "Int",
            "width": 60
        })

    return columns


def get_data(filters):
    month = int(filters.month)
    year = int(filters.year)
    days_in_month = calendar.monthrange(year, month)[1]

    ## Cap the last visible day to today if viewing the current month
    today = date.today()
    last_day_to_show = days_in_month
    if year == today.year and month == today.month:
        last_day_to_show = today.day

    from_date = "{}-{:02d}-01".format(year, month)
    to_date   = "{}-{:02d}-{:02d}".format(year, month, days_in_month)

    conditions = ""
    sle_filters = {
        "from_date": from_date,
        "to_date":   to_date
    }

    ## Build optional filters
    if filters.get("warehouse"):
        conditions += " AND sle.warehouse = %(warehouse)s"
        sle_filters["warehouse"] = filters.warehouse

    if filters.get("item_code"):
        conditions += " AND sle.item_code = %(item_code)s"
        sle_filters["item_code"] = filters.item_code

    if filters.get("item_group"):
        conditions += " AND i.item_group = %(item_group)s"
        sle_filters["item_group"] = filters.item_group

    ## Get distinct item + warehouse combinations active in this month
    pairs = frappe.db.sql("""
        SELECT DISTINCT sle.item_code, sle.warehouse
        FROM `tabStock Ledger Entry` sle
        INNER JOIN `tabItem` i ON i.name = sle.item_code
        WHERE sle.docstatus = 1
          AND DATE(sle.posting_date) BETWEEN %(from_date)s AND %(to_date)s
          {conditions}
        ORDER BY sle.item_code, sle.warehouse
    """.format(conditions=conditions), sle_filters, as_dict=True)

    if not pairs:
        return []

    data = []

    for row in pairs:
        item_code = row.item_code
        warehouse = row.warehouse

        ## Opening balance before the month starts
        opening_data = frappe.db.sql("""
            SELECT IFNULL(SUM(actual_qty), 0) as qty
            FROM `tabStock Ledger Entry`
            WHERE docstatus = 1
              AND item_code = %(item_code)s
              AND warehouse = %(warehouse)s
              AND DATE(posting_date) < %(from_date)s
        """, {"item_code": item_code, "warehouse": warehouse, "from_date": from_date}, as_dict=True)

        opening_qty = opening_data[0].qty if opening_data else 0

        ## Daily net movement within the month
        daily_data = frappe.db.sql("""
            SELECT DAY(posting_date) as day, SUM(actual_qty) as movement
            FROM `tabStock Ledger Entry`
            WHERE docstatus = 1
              AND item_code = %(item_code)s
              AND warehouse = %(warehouse)s
              AND DATE(posting_date) BETWEEN %(from_date)s AND %(to_date)s
            GROUP BY DAY(posting_date)
        """, {"item_code": item_code, "warehouse": warehouse, "from_date": from_date, "to_date": to_date}, as_dict=True)

        daily_movement = {d.day: d.movement for d in daily_data}

        entry = {
            "item_code": item_code,
            "warehouse": warehouse,
        }

        ## Cumulative balance per day, future days left blank
        running_balance = opening_qty
        for day in range(1, days_in_month + 1):
            if day > last_day_to_show:
                ## Future day - leave empty
                entry["day_{}".format(day)] = None
            else:
                running_balance += daily_movement.get(day, 0)
                entry["day_{}".format(day)] = int(round(running_balance, 0))

        data.append(entry)

    return data