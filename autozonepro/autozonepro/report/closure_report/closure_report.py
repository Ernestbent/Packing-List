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
	("daily_billed", "Billed"),
	("Billed", "Pending for Dispatch"),
	("daily_dispatched", "Dispatched"),
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
	# A Sales Order can retain its workflow_state while it is placed on hold.
	# Held orders must not be included in the active closure queues.
	state_totals = frappe.db.sql(
		"""
			SELECT
				workflow_state,
				COUNT(DISTINCT name) AS order_count,
				COALESCE(SUM(base_grand_total), 0) AS order_amount
			FROM `tabSales Order`
			WHERE company = %(company)s
				AND docstatus < 2
				AND IFNULL(status, '') NOT IN ('Hold', 'On Hold', 'Closed')
				AND workflow_state IN (
					'Pending Credit Approval', 'Approved', 'Picking',
					'Packing', 'Billed'
				)
			GROUP BY workflow_state
		""",
		{"company": filters.company},
		as_dict=True,
	)
	totals_by_state = {row.workflow_state: row for row in state_totals}

	## Pending for Dispatch is the current Billed queue. Its amount comes from the
	## submitted invoices linked to those Billed Sales Orders.
	pending_dispatch_invoice_rows = frappe.db.sql(
		"""
			SELECT
				DISTINCT si.name AS sales_invoice,
				si.base_grand_total,
				links.sales_order
			FROM (
				SELECT DISTINCT sales_order, parent AS sales_invoice
				FROM `tabSales Invoice Item`
				WHERE docstatus = 1 AND IFNULL(sales_order, '') != ''
			) links
			INNER JOIN `tabSales Invoice` si
				ON si.name = links.sales_invoice AND si.docstatus = 1
			INNER JOIN `tabSales Order` so ON so.name = links.sales_order
			WHERE so.company = %(company)s
				AND so.docstatus < 2
				AND IFNULL(so.status, '') NOT IN ('Hold', 'On Hold', 'Closed')
				AND so.workflow_state = 'Billed'
		""",
		{"company": filters.company},
		as_dict=True,
	)
	pending_dispatch_amount = sum(
		{row.sales_invoice: flt(row.base_grand_total) for row in pending_dispatch_invoice_rows}.values()
	)

	## Billed is daily throughput. Include every submitted Sales Invoice posted on
	## the selected date when it links to at least one Sales Order, regardless
	## of the Sales Order's creation date or its current workflow state.
	daily_billed_invoice_rows = frappe.db.sql(
		"""
			SELECT
				DISTINCT si.name AS sales_invoice,
				si.base_grand_total,
				sii.sales_order
			FROM `tabSales Invoice` si
			INNER JOIN `tabSales Invoice Item` sii
				ON sii.parent = si.name AND sii.docstatus = 1
			INNER JOIN `tabSales Order` so ON so.name = sii.sales_order
			WHERE si.docstatus = 1
				AND si.company = %(company)s
				AND si.posting_date = %(closing_date)s
				AND IFNULL(sii.sales_order, '') != ''
				AND so.docstatus < 2
				AND IFNULL(so.status, '') NOT IN ('Hold', 'On Hold', 'Closed')
		""",
		{
			"company": filters.company,
			"closing_date": filters.closing_date,
		},
		as_dict=True,
	)
	daily_billed = frappe._dict(
		order_count=len({row.sales_order for row in daily_billed_invoice_rows}),
		amount=sum(
			{row.sales_invoice: flt(row.base_grand_total) for row in daily_billed_invoice_rows}.values()
		),
	)

	## Dispatched is daily throughput. Use the audit trail so orders that moved on
	## to another workflow state are still counted on the day they were dispatched.
	dispatch_versions = frappe.db.sql(
		"""
			SELECT
				v.docname,
				v.data,
				so.base_grand_total
			FROM `tabVersion` v
			INNER JOIN `tabSales Order` so ON so.name = v.docname
			WHERE v.ref_doctype = 'Sales Order'
				AND v.creation >= %(period_start)s
				AND v.creation < %(period_end)s
				AND so.company = %(company)s
				AND so.docstatus < 2
				AND IFNULL(so.status, '') NOT IN ('Hold', 'On Hold', 'Closed')
				AND v.data LIKE '%%"workflow_state"%%Dispatched%%'
		""",
		{
			"company": filters.company,
			"period_start": get_datetime(filters.closing_date),
			"period_end": get_datetime(add_days(filters.closing_date, 1)),
		},
		as_dict=True,
	)
	dispatched_orders = {
		row.docname: flt(row.base_grand_total)
		for row in dispatch_versions
		if any(
			fieldname == "workflow_state" and new_value == "Dispatched"
			for fieldname, _old_value, new_value in get_version_changes(row.data)
		)
	}
	daily_dispatched = frappe._dict(
		order_count=len(dispatched_orders),
		amount=sum(dispatched_orders.values()),
	)

	return build_rows(
		totals_by_state,
		daily_billed,
		daily_dispatched,
		pending_dispatch_amount,
		filters.closing_date,
	)


def get_version_changes(version_data):
	try:
		data = json.loads(version_data or "{}")
	except (TypeError, ValueError):
		return []

	return [change[:3] for change in (data.get("changed") or []) if len(change) >= 3]


def build_rows(totals_by_state, daily_billed, daily_dispatched, pending_dispatch_amount, closing_date):
	period_remark = closing_date.strftime("%d %b")
	rows = []
	for idx, (report_key, label) in enumerate(WORKFLOW_STATES, start=1):
		state_total = totals_by_state.get(report_key) or frappe._dict()
		amount = flt(state_total.get("order_amount"))
		order_count = state_total.get("order_count") or 0
		if report_key == "daily_billed":
			amount = daily_billed.amount
			order_count = daily_billed.order_count
		elif report_key == "daily_dispatched":
			amount = daily_dispatched.amount
			order_count = daily_dispatched.order_count
		elif report_key == "Billed":
			amount = pending_dispatch_amount
		rows.append(
			{
				"idx": idx,
				"status": label,
				"amount": amount,
				"order_count": order_count,
				"remark": period_remark if report_key in ("daily_billed", "daily_dispatched") else "",
			}
		)
	return rows
