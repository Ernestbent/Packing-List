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

    ## Build optional item filters
    item_conditions = ""
    item_filters    = {}

    if filters.get("item_code"):
        item_conditions += " AND i.item_code = %(item_code)s"
        item_filters["item_code"] = filters.item_code

    if filters.get("item_group"):
        item_conditions += " AND i.item_group = %(item_group)s"
        item_filters["item_group"] = filters.item_group

    ## Pull ALL active items
    all_items = frappe.db.sql("""
        SELECT i.item_code
        FROM `tabItem` i
        WHERE i.disabled = 0
          {conditions}
        ORDER BY i.item_code
    """.format(conditions=item_conditions), item_filters, as_dict=True)

    if not all_items:
        return []

    ## Warehouse filter for SLE and Bin queries
    warehouse_filters   = {}
    warehouse_condition = ""
    if filters.get("warehouse"):
        warehouse_condition = " AND warehouse = %(warehouse)s"
        warehouse_filters["warehouse"] = filters.warehouse

    data = []

    for row in all_items:
        item_code = row.item_code

        ## Step 1: Get current live balance from tabBin (source of truth)
        bin_data = frappe.db.sql("""
            SELECT IFNULL(SUM(actual_qty), 0) AS qty
            FROM `tabBin`
            WHERE item_code = %(item_code)s
              {warehouse_condition}
        """.format(warehouse_condition=warehouse_condition),
        {**{"item_code": item_code}, **warehouse_filters},
        as_dict=True)

        current_live_qty = bin_data[0].qty if bin_data else 0

        ## Step 2: Get all SLE movements from day 1 of month up to today
        ## We need this to reconstruct each day's balance by working backwards
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

        ## Step 3: Get SLE movements AFTER today up to end of month
        ## These need to be excluded since tabBin already reflects them if any
        future_data = frappe.db.sql("""
            SELECT IFNULL(SUM(actual_qty), 0) AS qty
            FROM `tabStock Ledger Entry`
            WHERE docstatus = 1
              AND item_code = %(item_code)s
              AND DATE(posting_date) > %(today)s
              AND DATE(posting_date) <= %(to_date)s
              {warehouse_condition}
        """.format(warehouse_condition=warehouse_condition),
        {**{"item_code": item_code, "today": today.strftime("%Y-%m-%d"), "to_date": to_date}, **warehouse_filters},
        as_dict=True)

        future_qty = future_data[0].qty if future_data else 0

        ## Step 4: Balance at end of today = live bin qty minus any future movements
        balance_at_today = current_live_qty - future_qty

        ## Step 5: Work backwards from today to day 1 to get each day's closing balance
        ## day_balances[day] = closing balance at end of that day
        day_balances = {}
        running = balance_at_today

        for day in range(last_day_to_show, 0, -1):
            day_balances[day] = running
            ## Subtract this day's movement to get the previous day's closing balance
            running -= daily_movement.get(day, 0)

        entry = {
            "item_code": item_code,
            ## Show filtered warehouse or fall back to root warehouse group
            "warehouse": filters.get("warehouse") or "All Warehouses - APL",
        }

        ## Fill in each day - future days blank, past days from backwards calculation
        for day in range(1, days_in_month + 1):
            if day > last_day_to_show:
                ## Future day - leave empty
                entry["day_{}".format(day)] = None
            else:
                entry["day_{}".format(day)] = int(round(day_balances.get(day, 0), 0))

        data.append(entry)

    return data