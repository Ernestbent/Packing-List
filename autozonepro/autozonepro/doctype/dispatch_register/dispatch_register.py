# Copyright (c) 2026, Ernest Benedict and contributors
# For license information, please see license.txt

from contextlib import contextmanager

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, flt, get_datetime, getdate, now_datetime

from autozonepro.autozonepro.custom_scripts.exclusive_sales_order_item import (
	EXCLUSIVE_ITEM_CODE,
)


ALLOWED_ROLES = {"Remote User", "System Manager"}


@frappe.whitelist()
def get_delivery_note_customer(delivery_note):
	"""Return the display customer for a submitted Delivery Note."""
	_require_dispatch_access()

	delivery_note = (delivery_note or "").strip()
	if not delivery_note:
		return ""

	customer = frappe.db.get_value(
		"Delivery Note",
		{"name": delivery_note, "docstatus": 1},
		["customer_name", "customer"],
		as_dict=True,
	)
	if not customer:
		frappe.throw(_("Submitted Delivery Note {0} was not found.").format(delivery_note))

	return customer.customer_name or customer.customer


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_dispatch_ready_delivery_notes(doctype, txt, searchfield, start, page_len, filters):
	"""Delivery Notes created by the automatic flow and still awaiting dispatch."""
	_require_dispatch_access()

	posting_date = (filters or {}).get("posting_date")
	if not posting_date:
		return []

	return _find_dispatch_ready_delivery_notes(
		posting_date=getdate(posting_date),
		txt=txt,
		start=cint(start),
		page_len=cint(page_len),
	)


@frappe.whitelist()
def get_dispatch_history_suggestions(txt="", fieldname=""):
	"""Suggest previously submitted driver names or telephone numbers."""
	_require_dispatch_access()

	allowed_fields = {"driver_name", "telephone"}
	if fieldname not in allowed_fields:
		frappe.throw(_("Invalid dispatch suggestion field."), frappe.ValidationError)

	rows = frappe.db.sql(
		f"""
		SELECT drr.`{fieldname}` AS value
		FROM `tabDispatch Register Row` drr
		INNER JOIN `tabDispatch Register` dr
			ON dr.name = drr.parent
			AND drr.parenttype = 'Dispatch Register'
			AND drr.parentfield = 'rows'
			AND dr.docstatus = 1
		WHERE COALESCE(drr.`{fieldname}`, '') != ''
			AND drr.`{fieldname}` LIKE %(prefix)s
		GROUP BY drr.`{fieldname}`
		ORDER BY MAX(dr.date_time) DESC, MAX(dr.posting__time) DESC, MAX(drr.modified) DESC
		LIMIT 20
		""",
		{"prefix": f"{(txt or '').strip()}%"},
		as_dict=True,
	)
	return [row.value for row in rows]


@frappe.whitelist()
def get_dispatch_register_list(
	customer="", dispatch_date="", delivery_note="", limit_start=0, limit=10
):
	"""Return permitted register records matching parent and child-row filters."""
	_require_dispatch_access()

	customer = (customer or "").strip()
	delivery_note = (delivery_note or "").strip()
	limit_start = max(cint(limit_start), 0)
	limit = min(max(cint(limit), 1), 50)
	filters = {}

	if dispatch_date:
		selected_date = getdate(dispatch_date)
		filters["date_time"] = [
			"between",
			[f"{selected_date} 00:00:00", f"{selected_date} 23:59:59.999999"],
		]

	registers = frappe.get_list(
		"Dispatch Register",
		filters=filters,
		fields=["name", "status", "date_time", "total_bundles", "total_expense"],
		order_by="date_time desc, creation desc",
		limit_page_length=0,
	)

	if (customer or delivery_note) and registers:
		row_filters = {
			"parent": ["in", [register.name for register in registers]],
			"parenttype": "Dispatch Register",
		}
		if customer:
			row_filters["customer_name"] = ["like", f"%{customer}%"]
		if delivery_note:
			row_filters["delivery_note"] = ["like", f"%{delivery_note}%"]

		matching_registers = set(
			frappe.get_all(
				"Dispatch Register Row",
				filters=row_filters,
				pluck="parent",
			)
		)
		registers = [register for register in registers if register.name in matching_registers]

	return registers[limit_start : limit_start + limit]


class DispatchRegister(Document):
	def before_insert(self):
		if not self.date_time:
			self.date_time = now_datetime()
		if not self.posting__time:
			self.posting__time = now_datetime().time()

		if frappe.flags.in_web_form:
			_require_dispatch_access()
			self.submitted_by = frappe.session.user
			self.third_party = frappe.session.user
			# Web Form inserts documents. Convert that insert into a submitted
			# register so each row is processed exactly once.
			self.docstatus = 1
			self._action = "submit"
			self.set_docstatus()

	def validate(self):
		if not self.date_time:
			self.date_time = now_datetime()
		if not self.posting__time:
			self.posting__time = now_datetime().time()
		if not self.submitted_by:
			self.submitted_by = frappe.session.user
		if not self.third_party:
			self.third_party = self.submitted_by

		self._validate_and_enrich_rows()
		self._set_totals()

	def before_submit(self):
		self._process_rows()
		self._set_totals()

	def _validate_and_enrich_rows(self):
		if not self.rows:
			frappe.throw(_("Please add at least one Delivery Note."))

		seen_delivery_notes = set()
		for row in self.rows:
			if not row.delivery_note:
				frappe.throw(_("Delivery Note is required in row {0}.").format(row.idx))
			if row.delivery_note in seen_delivery_notes:
				frappe.throw(
					_("Delivery Note {0} appears more than once in this register.").format(
						frappe.bold(row.delivery_note)
					)
				)
			seen_delivery_notes.add(row.delivery_note)

			for fieldname, label in (
				("driver_name", _("Driver Name")),
				("vehicle_number", _("Vehicle Number")),
				("telephone", _("Telephone Number")),
			):
				if not (row.get(fieldname) or "").strip():
					frappe.throw(_("{0} is required in row {1}.").format(label, row.idx))

			if cint(row.number_of_bundles) <= 0:
				frappe.throw(_("Number of Bundles must be above 0 in row {0}.").format(row.idx))
			if row.total_expense is None or flt(row.total_expense) < 0:
				frappe.throw(_("Total Expense cannot be negative in row {0}.").format(row.idx))

			row.number_of_bundles = cint(row.number_of_bundles)
			row.total_expense = flt(row.total_expense, 2)
			row.cost_per_bundle = flt(row.total_expense / row.number_of_bundles, 2)
			row.row_status = row.row_status or "Pending"

			# Customer and Sales Order are always derived on the server; browser
			# values are display conveniences and are never trusted.
			details = get_delivery_note_details(
				row.delivery_note,
				posting_date=self.date_time,
				require_dispatch_ready=True,
			)
			row.customer_name = details.customer
			row.sales_order = details.sales_order

	def _set_totals(self):
		self.total_bundles = sum(cint(row.number_of_bundles) for row in self.rows)
		self.total_expense = flt(sum(flt(row.total_expense) for row in self.rows), 2)

	def _process_rows(self):
		failed = False
		for row in self.rows:
			savepoint = f"dispatch_register_row_{row.idx}"
			frappe.db.savepoint(savepoint)
			try:
				shipment = self._create_shipment(row)
				row.row_status = "Dispatched"
				row.row_message = _("Sales Order {0} moved to Dispatched.").format(
					row.sales_order
				)
				row.third_party_shipment = shipment.name
			except Exception as error:
				frappe.db.rollback(save_point=savepoint)
				frappe.clear_messages()
				failed = True
				row.row_status = "Failed"
				row.row_message = _clean_error_message(error)
				row.third_party_shipment = None
			finally:
				frappe.db.release_savepoint(savepoint)

		self.status = "Partially Failed" if failed else "Submitted"

	def _create_shipment(self, row):
		register_datetime = get_datetime(f"{self.date_time} {self.posting__time}")
		shipment = frappe.get_doc(
			{
				"doctype": "Third-Party Shipment",
				"delivery_note": row.delivery_note,
				"date": register_datetime.date(),
				"time": register_datetime.time(),
				"driver": row.driver_name,
				"tel_no": row.telephone,
				"vehicle_number": row.vehicle_number,
				"table_qwyw": [
					{"bundle": f"Bundle {index}", "expense": expense}
					for index, expense in enumerate(
						bundle_expenses(row.total_expense, row.number_of_bundles), start=1
					)
				],
			}
		)
		shipment.flags.from_dispatch_register = True
		with _without_web_form_flag():
			shipment.insert(ignore_permissions=True)
			shipment.submit()
		return shipment


def get_delivery_note_details(
	delivery_note, posting_date=None, require_dispatch_ready=False
):
	delivery_note_doc = frappe.get_doc("Delivery Note", delivery_note)
	if delivery_note_doc.docstatus != 1:
		frappe.throw(_("Delivery Note {0} must be submitted.").format(delivery_note))

	sales_orders = sorted(
		{row.against_sales_order for row in delivery_note_doc.items if row.against_sales_order}
	)
	if not sales_orders:
		frappe.throw(_("Delivery Note {0} is not linked to a Sales Order.").format(delivery_note))
	if len(sales_orders) > 1:
		frappe.throw(
			_("Delivery Note {0} is linked to multiple Sales Orders.").format(delivery_note)
		)

	if require_dispatch_ready:
		matching_notes = _find_dispatch_ready_delivery_notes(
			posting_date=getdate(posting_date),
			delivery_note=delivery_note,
			page_len=1,
			as_dict=True,
		)
		if not matching_notes:
			frappe.throw(
				_(
					"Delivery Note {0} is not an automatically completed note awaiting dispatch for {1}."
				).format(frappe.bold(delivery_note), frappe.bold(getdate(posting_date)))
			)

	return frappe._dict(
		customer=delivery_note_doc.customer_name or delivery_note_doc.customer,
		sales_order=sales_orders[0],
	)


def _find_dispatch_ready_delivery_notes(
	posting_date, txt="", delivery_note="", start=0, page_len=20, as_dict=False
):
	return frappe.db.sql(
		"""
		SELECT DISTINCT
			dn.name AS delivery_note,
			COALESCE(NULLIF(dn.customer_name, ''), dn.customer) AS customer_name,
			so.name AS sales_order
		FROM `tabDelivery Note` dn
		INNER JOIN `tabDelivery Note Item` dni
			ON dni.parent = dn.name
			AND dni.parenttype = 'Delivery Note'
		INNER JOIN `tabSales Order` so
			ON so.name = dni.against_sales_order
		INNER JOIN `tabSales Invoice Item` sii
			ON sii.delivery_note = dn.name
			AND sii.sales_order = so.name
		INNER JOIN `tabSales Invoice` si
			ON si.name = sii.parent
			AND si.docstatus = 1
		WHERE dn.docstatus = 1
			AND dn.status = 'Completed'
			AND dn.posting_date = %(posting_date)s
			AND so.workflow_state = 'In Transit'
			AND dni.item_code = %(item_code)s
			AND (
				SELECT COUNT(*)
				FROM `tabSales Order Item` soi
				WHERE soi.parent = so.name
					AND soi.parenttype = 'Sales Order'
			) = 1
			AND EXISTS (
				SELECT 1
				FROM `tabComment` comment
				WHERE comment.reference_doctype = 'Sales Order'
					AND comment.reference_name = so.name
					AND comment.comment_type = 'Comment'
					AND comment.content LIKE CONCAT(
						'%%Automatically created Delivery Note%%', dn.name, '%%Sales Invoice%%'
					)
			)
			AND NOT EXISTS (
				SELECT 1
				FROM `tabThird-Party Shipment` shipment
				WHERE shipment.delivery_note = dn.name
			)
			AND (%(delivery_note)s = '' OR dn.name = %(delivery_note)s)
			AND (
				dn.name LIKE %(txt)s
				OR dn.customer_name LIKE %(txt)s
				OR dn.customer LIKE %(txt)s
				OR so.name LIKE %(txt)s
			)
		ORDER BY dn.posting_time DESC, dn.name DESC
		LIMIT %(start)s, %(page_len)s
		""",
		{
			"posting_date": posting_date,
			"item_code": EXCLUSIVE_ITEM_CODE,
			"delivery_note": delivery_note or "",
			"txt": f"%{txt or ''}%",
			"start": max(cint(start), 0),
			"page_len": min(max(cint(page_len), 1), 100),
		},
		as_dict=as_dict,
	)


def bundle_expenses(total_expense, number_of_bundles):
	"""Split a total across bundles without losing a rounding remainder."""
	count = cint(number_of_bundles)
	if count <= 0:
		return []

	total = flt(total_expense, 2)
	average = flt(total / count, 2)
	expenses = [average] * count
	expenses[-1] = flt(total - sum(expenses[:-1]), 2)
	return expenses


@contextmanager
def _without_web_form_flag():
	was_in_web_form = getattr(frappe.flags, "in_web_form", False)
	frappe.flags.in_web_form = False
	try:
		yield
	finally:
		frappe.flags.in_web_form = was_in_web_form


def _clean_error_message(error):
	message = str(error).strip() or _("This row could not be dispatched.")
	return frappe.utils.strip_html(message)[:1000]


def _require_dispatch_access():
	if frappe.session.user == "Guest":
		frappe.throw(_("Please log in to use the dispatch register."), frappe.AuthenticationError)
	if not ALLOWED_ROLES.intersection(frappe.get_roles()):
		frappe.throw(_("You are not permitted to use the dispatch register."), frappe.PermissionError)
