from datetime import timedelta

import frappe
from frappe import _
from frappe.utils import formatdate, getdate


def execute(filters=None):
	filters = frappe._dict(filters or {})
	validate_filters(filters)

	columns = get_columns(filters)
	data = get_data(filters)
	return columns, data


def validate_filters(filters):
	if not filters.from_date or not filters.to_date:
		frappe.throw(_("Please select From Date and To Date"))

	if getdate(filters.from_date) > getdate(filters.to_date):
		frappe.throw(_("From Date cannot be after To Date"))


def get_date_range(filters):
	current_date = getdate(filters.from_date)
	to_date = getdate(filters.to_date)
	dates = []

	while current_date <= to_date:
		dates.append(current_date)
		current_date += timedelta(days=1)

	return dates


def get_date_fieldname(stock_date):
	return f"date_{stock_date.strftime('%Y_%m_%d')}"


def get_columns(filters):
	columns = [
		{
			"label": _("Item Code"),
			"fieldname": "item_code",
			"fieldtype": "Link",
			"options": "Item",
			"width": 180,
		},
		{
			"label": _("Warehouse"),
			"fieldname": "warehouse",
			"fieldtype": "Link",
			"options": "Warehouse",
			"width": 180,
		},
	]

	for stock_date in get_date_range(filters):
		columns.append(
			{
				"label": formatdate(stock_date, "dd MMM yyyy"),
				"fieldname": get_date_fieldname(stock_date),
				"fieldtype": "Int",
				"width": 105,
			}
		)

	return columns


def get_item_conditions(filters):
	conditions = ""
	query_filters = {}

	if filters.get("item_code"):
		conditions += " AND i.item_code = %(item_code)s"
		query_filters["item_code"] = filters.item_code

	if filters.get("item_group"):
		conditions += " AND i.item_group = %(item_group)s"
		query_filters["item_group"] = filters.item_group

	return conditions, query_filters


def get_data(filters):
	date_range = get_date_range(filters)
	item_conditions, query_filters = get_item_conditions(filters)
	query_filters.update(
		{
			"from_date": getdate(filters.from_date),
			"to_date": getdate(filters.to_date),
		}
	)

	warehouse_condition = ""
	if filters.get("warehouse"):
		warehouse_condition = " AND sle.warehouse = %(warehouse)s"
		query_filters["warehouse"] = filters.warehouse

	items = frappe.db.sql(
		"""
		SELECT i.item_code
		FROM `tabItem` i
		WHERE i.disabled = 0
		  {item_conditions}
		ORDER BY i.item_code
		""".format(item_conditions=item_conditions),
		query_filters,
		as_dict=True,
	)

	if not items:
		return []

	# Closing stock on the day before From Date.
	opening_rows = frappe.db.sql(
		"""
		SELECT sle.item_code, IFNULL(SUM(sle.actual_qty), 0) AS qty
		FROM `tabStock Ledger Entry` sle
		INNER JOIN `tabItem` i ON i.item_code = sle.item_code
		WHERE sle.docstatus = 1
		  AND sle.posting_date < %(from_date)s
		  {warehouse_condition}
		  {item_conditions}
		GROUP BY sle.item_code
		""".format(
			warehouse_condition=warehouse_condition,
			item_conditions=item_conditions,
		),
		query_filters,
		as_dict=True,
	)
	opening_balances = {row.item_code: row.qty for row in opening_rows}

	# One bulk query supplies every movement in the requested range. This avoids
	# running separate Stock Ledger and Bin queries for every individual item.
	movement_rows = frappe.db.sql(
		"""
		SELECT sle.item_code, sle.posting_date, SUM(sle.actual_qty) AS movement
		FROM `tabStock Ledger Entry` sle
		INNER JOIN `tabItem` i ON i.item_code = sle.item_code
		WHERE sle.docstatus = 1
		  AND sle.posting_date BETWEEN %(from_date)s AND %(to_date)s
		  {warehouse_condition}
		  {item_conditions}
		GROUP BY sle.item_code, sle.posting_date
		ORDER BY sle.item_code, sle.posting_date
		""".format(
			warehouse_condition=warehouse_condition,
			item_conditions=item_conditions,
		),
		query_filters,
		as_dict=True,
	)

	movements = {}
	for row in movement_rows:
		movements.setdefault(row.item_code, {})[getdate(row.posting_date)] = row.movement

	data = []
	for item in items:
		running_balance = opening_balances.get(item.item_code, 0)
		item_movements = movements.get(item.item_code, {})
		entry = {
			"item_code": item.item_code,
			"warehouse": filters.get("warehouse") or "All Warehouses - APL",
		}

		for stock_date in date_range:
			running_balance += item_movements.get(stock_date, 0)
			entry[get_date_fieldname(stock_date)] = int(round(running_balance))

		data.append(entry)

	return data
