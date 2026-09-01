from datetime import timedelta

import frappe
from frappe import _
from frappe.utils import formatdate, getdate, nowdate
from frappe.utils.nestedset import get_descendants_of


def execute(filters=None):
	filters = frappe._dict(filters or {})
	validate_filters(filters)

	return get_columns(filters), get_data(filters)


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
				"fieldtype": "Float",
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


def get_warehouse_condition(filters, table_alias, query_filters):
	warehouse = filters.get("warehouse")
	if not warehouse:
		return ""

	warehouses = [warehouse]
	if frappe.db.get_value("Warehouse", warehouse, "is_group"):
		warehouses.extend(get_descendants_of("Warehouse", warehouse, ignore_permissions=True))

	query_filters["warehouses"] = tuple(warehouses)
	return f" AND {table_alias}.warehouse IN %(warehouses)s"


def get_current_bin_balances(filters, item_conditions, query_filters):
	bin_filters = query_filters.copy()
	warehouse_condition = get_warehouse_condition(filters, "sbin", bin_filters)

	rows = frappe.db.sql(
		"""
		SELECT i.item_code, COALESCE(SUM(sbin.actual_qty), 0) AS qty
		FROM `tabItem` i
		LEFT JOIN `tabBin` sbin ON sbin.item_code = i.item_code
		WHERE i.disabled = 0
		  {warehouse_condition}
		  {item_conditions}
		GROUP BY i.item_code
		""".format(
			warehouse_condition=warehouse_condition,
			item_conditions=item_conditions,
		),
		bin_filters,
		as_dict=True,
	)

	return {row.item_code: row.qty for row in rows}


def get_data(filters):
	date_range = get_date_range(filters)
	item_conditions, query_filters = get_item_conditions(filters)
	query_filters.update(
		{
			"from_date": getdate(filters.from_date),
			"to_date": getdate(filters.to_date),
		}
	)

	warehouse_condition = get_warehouse_condition(filters, "sle", query_filters)
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

	# Historical opening balance: use the last canonical, non-cancelled ledger
	# balance for every item and warehouse before the selected range.
	opening_rows = frappe.db.sql(
		"""
		SELECT item_code, warehouse, qty_after_transaction AS qty
		FROM (
			SELECT
				sle.item_code,
				sle.warehouse,
				sle.qty_after_transaction,
				ROW_NUMBER() OVER (
					PARTITION BY sle.item_code, sle.warehouse
					ORDER BY sle.posting_datetime DESC, sle.creation DESC
				) AS row_idx
			FROM `tabStock Ledger Entry` sle
			INNER JOIN `tabItem` i ON i.item_code = sle.item_code
			WHERE sle.is_cancelled = 0
			  AND sle.posting_date < %(from_date)s
			  {warehouse_condition}
			  {item_conditions}
		) opening_sle
		WHERE row_idx = 1
		""".format(
			warehouse_condition=warehouse_condition,
			item_conditions=item_conditions,
		),
		query_filters,
		as_dict=True,
	)

	warehouse_balances = {}
	for row in opening_rows:
		warehouse_balances.setdefault(row.item_code, {})[row.warehouse] = row.qty

	# For each historical day, ERPNext's final qty_after_transaction is the
	# authoritative closing quantity for that item and warehouse.
	daily_closing_rows = frappe.db.sql(
		"""
		SELECT item_code, warehouse, posting_date, qty_after_transaction AS qty
		FROM (
			SELECT
				sle.item_code,
				sle.warehouse,
				sle.posting_date,
				sle.qty_after_transaction,
				ROW_NUMBER() OVER (
					PARTITION BY sle.item_code, sle.warehouse, sle.posting_date
					ORDER BY sle.posting_datetime DESC, sle.creation DESC
				) AS row_idx
			FROM `tabStock Ledger Entry` sle
			INNER JOIN `tabItem` i ON i.item_code = sle.item_code
			WHERE sle.is_cancelled = 0
			  AND sle.posting_date BETWEEN %(from_date)s AND %(to_date)s
			  {warehouse_condition}
			  {item_conditions}
		) daily_sle
		WHERE row_idx = 1
		ORDER BY item_code, posting_date, warehouse
		""".format(
			warehouse_condition=warehouse_condition,
			item_conditions=item_conditions,
		),
		query_filters,
		as_dict=True,
	)

	daily_closings = {}
	for row in daily_closing_rows:
		daily_closings.setdefault(row.item_code, {}).setdefault(
			getdate(row.posting_date), []
		).append((row.warehouse, row.qty))

	# Today's quantity must agree exactly with Daily Stock Level and Stock Bin.
	current_date = getdate(nowdate())
	current_bin_balances = {}
	if current_date in date_range:
		current_bin_balances = get_current_bin_balances(
			filters, item_conditions, query_filters
		)

	data = []
	for item in items:
		item_warehouse_balances = warehouse_balances.get(item.item_code, {}).copy()
		item_daily_closings = daily_closings.get(item.item_code, {})
		entry = {
			"item_code": item.item_code,
			"warehouse": filters.get("warehouse") or "All Warehouses - APL",
		}

		for stock_date in date_range:
			for warehouse, closing_qty in item_daily_closings.get(stock_date, []):
				item_warehouse_balances[warehouse] = closing_qty

			closing_balance = sum(item_warehouse_balances.values())
			if stock_date == current_date:
				closing_balance = current_bin_balances.get(item.item_code, 0)

			entry[get_date_fieldname(stock_date)] = closing_balance

		data.append(entry)

	return data
