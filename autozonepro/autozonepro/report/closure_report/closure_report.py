# Copyright (c) 2026, Ernest Benedict and contributors
# For license information, please see license.txt

import json

import frappe
from frappe import _
from frappe.utils import add_days, flt, get_datetime, getdate, nowdate


WORKFLOW_STATES = [
	("Pending Credit Approval", "Pending Credit Approval"),
	("Approved", "Approved"),
	("Picking", "Picking"),
	("Packing", "Packing"),
	("Billed", "Billed"),
	("In Transit", "Pending for Dispatch"),
]


def execute(filters=None):
	filters = frappe._dict(filters or {})
	validate_filters(filters)
	return get_columns(), get_data(filters)


def validate_filters(filters):
	if not filters.get("company"):
		frappe.throw(_("Company is required"))

	filters.closing_date = getdate(filters.get("closing_date") or nowdate())
	if filters.closing_date > getdate(nowdate()):
		frappe.throw(_("Closing Date cannot be in the future"))


def get_columns():
	return [
		{"label": _("#"), "fieldname": "idx", "fieldtype": "Int", "width": 50},
		{"label": _("Status"), "fieldname": "status", "fieldtype": "Data", "width": 220},
		{"label": _("Amount"), "fieldname": "amount", "fieldtype": "Currency", "width": 160},
		{
			"label": _("Count of Order"),
			"fieldname": "order_count",
			"fieldtype": "Int",
			"width": 130,
		},
		{"label": _("Remark"), "fieldname": "remark", "fieldtype": "Data", "width": 220},
	]


def get_data(filters):
	period_start = get_datetime(filters.closing_date)
	period_end = get_datetime(add_days(filters.closing_date, 1))

	orders = frappe.db.sql(
		"""
			SELECT name, workflow_state, base_grand_total
			FROM `tabSales Order`
			WHERE company = %(company)s
				AND creation < %(period_end)s
		""",
		{"company": filters.company, "period_end": period_end},
		as_dict=True,
	)
	if not orders:
		return build_rows({}, set(), {}, filters.closing_date)

	state_at_close = {order.name: order.workflow_state for order in orders}
	amount_at_close = {order.name: flt(order.base_grand_total) for order in orders}

	# Version is the audit trail. Reading from newest to oldest lets us reverse
	# changes made after the selected day's midnight and recover that day's state.
	versions = frappe.db.sql(
		"""
			SELECT v.docname, v.creation, v.data
			FROM `tabVersion` v
			INNER JOIN `tabSales Order` so ON so.name = v.docname
			WHERE v.ref_doctype = 'Sales Order'
				AND so.company = %(company)s
				AND so.creation < %(period_end)s
				AND v.creation >= %(period_start)s
			ORDER BY v.creation DESC
		""",
		{
			"company": filters.company,
			"period_start": period_start,
			"period_end": period_end,
		},
		as_dict=True,
	)

	billed_orders = set()
	for version in versions:
		changes = get_version_changes(version.data)
		if period_start <= version.creation < period_end:
			for fieldname, old_value, new_value in changes:
				if fieldname == "workflow_state" and old_value == "Billing" and new_value == "Billed":
					billed_orders.add(version.docname)

		if version.creation < period_end:
			continue

		for fieldname, old_value, _new_value in changes:
			if fieldname == "workflow_state":
				state_at_close[version.docname] = old_value
			elif fieldname == "base_grand_total":
				amount_at_close[version.docname] = flt(old_value)

	return build_rows(state_at_close, billed_orders, amount_at_close, filters.closing_date)


def get_version_changes(version_data):
	try:
		data = json.loads(version_data or "{}")
	except (TypeError, ValueError):
		return []

	changes = []
	for change in data.get("changed") or []:
		if len(change) >= 3:
			changes.append((change[0], change[1], change[2]))
	return changes


def build_rows(state_at_close, billed_orders, amount_at_close, closing_date):
	state_orders = frappe._dict()
	for order_name, workflow_state in state_at_close.items():
		state_orders.setdefault(workflow_state, set()).add(order_name)

	period_remark = "{0} to {1}".format(
		closing_date.strftime("%d %b"), add_days(closing_date, 1).strftime("%d %b")
	)
	rows = []
	for idx, (workflow_state, label) in enumerate(WORKFLOW_STATES, start=1):
		order_names = billed_orders if workflow_state == "Billed" else state_orders.get(workflow_state, set())
		rows.append(
			{
				"idx": idx,
				"status": label,
				"amount": sum(amount_at_close.get(name, 0) for name in order_names),
				"order_count": len(order_names),
				"remark": period_remark if workflow_state == "Billed" else "",
			}
		)
	return rows
