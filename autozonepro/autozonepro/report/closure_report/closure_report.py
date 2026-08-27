# Copyright (c) 2026, Ernest Benedict and contributors
# For license information, please see license.txt

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

	state_totals = frappe.db.sql(
		"""
			SELECT
				workflow_state,
				COUNT(DISTINCT name) AS order_count,
				COALESCE(SUM(base_grand_total), 0) AS order_amount
			FROM `tabSales Order`
			WHERE company = %(company)s
				AND docstatus < 2
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

	# Pending for Dispatch is the current Billed queue. Its amount comes from the
	# submitted invoices linked to those Billed Sales Orders.
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
				AND so.workflow_state = 'Billed'
		""",
		{"company": filters.company},
		as_dict=True,
	)
	pending_dispatch_amount = sum(
		{row.sales_invoice: flt(row.base_grand_total) for row in pending_dispatch_invoice_rows}.values()
	)

	# Billed is daily throughput. Include every submitted Sales Invoice worked on
	# during the selected date window when it links to at least one Sales Order,
	# regardless of the Sales Order's creation date or its current workflow state.
	daily_billed_invoice_rows = frappe.db.sql(
		"""
			SELECT
				DISTINCT si.name AS sales_invoice,
				si.base_grand_total,
				sii.sales_order
			FROM `tabSales Invoice` si
			INNER JOIN `tabSales Invoice Item` sii
				ON sii.parent = si.name AND sii.docstatus = 1
			WHERE si.docstatus = 1
				AND si.company = %(company)s
				AND si.modified >= %(period_start)s
				AND si.modified < %(period_end)s
				AND IFNULL(sii.sales_order, '') != ''
		""",
		{
			"company": filters.company,
			"period_start": period_start,
			"period_end": period_end,
		},
		as_dict=True,
	)
	daily_billed = frappe._dict(
		order_count=len({row.sales_order for row in daily_billed_invoice_rows}),
		amount=sum(
			{row.sales_invoice: flt(row.base_grand_total) for row in daily_billed_invoice_rows}.values()
		),
	)

	return build_rows(
		totals_by_state,
		daily_billed,
		pending_dispatch_amount,
		filters.closing_date,
	)


def build_rows(totals_by_state, daily_billed, pending_dispatch_amount, closing_date):
	period_remark = "{0} to {1}".format(
		closing_date.strftime("%d %b"), add_days(closing_date, 1).strftime("%d %b")
	)
	rows = []
	for idx, (report_key, label) in enumerate(WORKFLOW_STATES, start=1):
		state_total = totals_by_state.get(report_key) or frappe._dict()
		amount = flt(state_total.get("order_amount"))
		order_count = state_total.get("order_count") or 0
		if report_key == "daily_billed":
			amount = daily_billed.amount
			order_count = daily_billed.order_count
		elif report_key == "Billed":
			amount = pending_dispatch_amount
		rows.append(
			{
				"idx": idx,
				"status": label,
				"amount": amount,
				"order_count": order_count,
				"remark": period_remark if report_key == "daily_billed" else "",
			}
		)
	return rows
