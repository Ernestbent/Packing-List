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
    year  = int(filters.year)
    days_in_month = calendar.monthrange(year, month)[1]

    ## Cap the last visible day to today if viewing the current month
    today = date.today()
    last_day_to_show = days_in_month
    if year == today.year and month == today.month:
        last_day_to_show = today.day

    from_date = "{}-{:02d}-01".format(year, month)
    to_date   = "{}-{:02d}-{:02d}".format(year, month, days_in_month)

    ## Build optional filters
    item_conditions = ""
    item_filters    = {}

    if filters.get("item_code"):
        item_conditions += " AND i.item_code = %(item_code)s"
        item_filters["item_code"] = filters.item_code

    if filters.get("item_group"):
        item_conditions += " AND i.item_group = %(item_group)s"
        item_filters["item_group"] = filters.item_group

    ## Pull ALL items from tabItem regardless of stock or warehouse
    all_items = frappe.db.sql("""
        SELECT i.item_code
        FROM `tabItem` i
        WHERE i.disabled = 0
          {conditions}
        ORDER BY i.item_code
    """.format(conditions=item_conditions), item_filters, as_dict=True)

    if not all_items:
        return []

    ## Warehouse filter applied to stock ledger queries
    warehouse_filters    = {}
    warehouse_condition  = ""
    if filters.get("warehouse"):
        warehouse_condition = " AND warehouse = %(warehouse)s"
        warehouse_filters["warehouse"] = filters.warehouse

    data = []

    for row in all_items:
        item_code = row.item_code

        ## Opening balance before the month across all warehouses (or filtered warehouse)
        opening_data = frappe.db.sql("""
            SELECT IFNULL(SUM(actual_qty), 0) AS qty
            FROM `tabStock Ledger Entry`
            WHERE docstatus = 1
              AND item_code = %(item_code)s
              AND DATE(posting_date) < %(from_date)s
              {warehouse_condition}
        """.format(warehouse_condition=warehouse_condition),
        {**{"item_code": item_code, "from_date": from_date}, **warehouse_filters},
        as_dict=True)

        opening_qty = opening_data[0].qty if opening_data else 0

        ## Daily net movement within the month across all warehouses (or filtered warehouse)
        daily_data = frappe.db.sql("""
            SELECT DAY(posting_date) AS day, SUM(actual_qty) AS movement
            FROM `tabStock Ledger Entry`
            WHERE docstatus = 1
              AND item_code = %(item_code)s
              AND DATE(posting_date) BETWEEN %(from_date)s AND %(to_date)s
              {warehouse_condition}
            GROUP BY DAY(posting_date)
        """.format(warehouse_condition=warehouse_condition),
        {**{"item_code": item_code, "from_date": from_date, "to_date": to_date}, **warehouse_filters},
        as_dict=True)

        daily_movement = {d.day: d.movement for d in daily_data}

        entry = {
            "item_code": item_code,
            ## Show filtered warehouse or fall back to root warehouse group
            "warehouse": filters.get("warehouse") or "All Warehouses - APL",
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