# Copyright (c) 2026, Ernest Benedict and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.model.workflow import apply_workflow, get_transitions
from frappe.utils import flt, get_fullname

from autozonepro.autozonepro.custom_scripts.exclusive_sales_order_item import (
	EXCLUSIVE_ITEM_CODE,
	is_exclusive_item_order,
)


COURIER_DETAILS_ACTION = "Enter Courier Details"
DISPATCHED_STATE = "Dispatched"


class ThirdPartyShipment(Document):
	def before_insert(self):
		"""Submit new Web Form responses instead of leaving them as drafts."""
		if not frappe.flags.in_web_form:
			return

		allowed_roles = {"Remote User", "System Manager"}
		if not allowed_roles.intersection(frappe.get_roles()):
			frappe.throw(
				_("You are not permitted to submit shipment details."),
				frappe.PermissionError,
			)

		# Frappe's Web Form endpoint only inserts documents. Mark this insert as a
		# submit action so validation and on_submit run once in the same transaction.
		self.docstatus = 1
		self._action = "submit"
		self.set_docstatus()

	def validate(self):
		self.set_delivery_note_details()
		self.validate_unique_delivery_note()
		self.validate_courier_details()
		self.calculate_bundle_total()

	def on_submit(self):
		self.create_or_update_courier_details()
		self.dispatch_sales_order()

	def set_delivery_note_details(self):
		if not self.delivery_note:
			frappe.throw(_("Delivery Note is required."))

		delivery_note = frappe.get_doc("Delivery Note", self.delivery_note)
		if delivery_note.docstatus != 1:
			frappe.throw(_("Delivery Note {0} must be submitted.").format(self.delivery_note))

		self.customer = delivery_note.customer
		sales_orders = sorted(
			{row.against_sales_order for row in delivery_note.items if row.against_sales_order}
		)

		if not sales_orders:
			frappe.throw(
				_("Delivery Note {0} is not linked to a Sales Order.").format(self.delivery_note)
			)
		if len(sales_orders) > 1:
			frappe.throw(
				_("Delivery Note {0} is linked to multiple Sales Orders and cannot be mapped automatically.").format(
					self.delivery_note
				)
			)

		self.sales_order = sales_orders[0]

	def validate_unique_delivery_note(self):
		existing_shipment = frappe.db.get_value(
			"Third-Party Shipment",
			{
				"delivery_note": self.delivery_note,
				"name": ["!=", self.name],
			},
			"name",
		)
		if existing_shipment:
			frappe.throw(
				_(
					"Courier details have already been submitted for Delivery Note {0}."
				).format(frappe.bold(self.delivery_note)),
				title=_("Courier Details Already Submitted"),
			)

	def validate_courier_details(self):
		for fieldname, label in (
			("driver", _("Driver")),
			("tel_no", _("Telephone Number")),
			("vehicle_number", _("Vehicle Number")),
		):
			if not self.get(fieldname):
				frappe.throw(_("{0} is required.").format(label))

		if not self.table_qwyw:
			frappe.throw(_("Please enter at least one bundle."))

	def calculate_bundle_total(self):
		self.total_expense = 0
		for index, row in enumerate(self.table_qwyw, start=1):
			row.bundle = _("Bundle {0}").format(index)
			if flt(row.expense) < 0:
				frappe.throw(_("Expense for Bundle {0} cannot be negative.").format(index))
			self.total_expense += flt(row.expense)

	def create_or_update_courier_details(self):
		courier_name = frappe.db.get_value(
			"Courier Details", {"custom_sales_order": self.sales_order}, "name"
		)
		courier = (
			frappe.get_doc("Courier Details", courier_name)
			if courier_name
			else frappe.new_doc("Courier Details")
		)

		courier.update(
			{
				"first_name": self.driver,
				"tel_no": self.tel_no,
				"vehicle_no": self.vehicle_number,
				"custom_sales_order": self.sales_order,
				"total_expense": self.total_expense,
			}
		)
		courier.set("bundle_details", [])
		for row in self.table_qwyw:
			courier.append(
				"bundle_details",
				{"bundle": row.bundle, "expense": row.expense},
			)

		if courier.is_new():
			courier.insert(ignore_permissions=True)
		else:
			courier.save(ignore_permissions=True)

		self.db_set("courier_details", courier.name, update_modified=False)

	def dispatch_sales_order(self):
		"""Use the active Sales Order workflow after courier details are saved."""
		sales_order = frappe.get_doc("Sales Order", self.sales_order)
		actor_user = self.owner or frappe.session.user
		actor_name = get_fullname(actor_user) or actor_user
		if not is_exclusive_item_order(sales_order):
			frappe.throw(
				_(
					"Sales Order {0} is not a third-party shipment for item {1}."
				).format(frappe.bold(sales_order.name), frappe.bold(EXCLUSIVE_ITEM_CODE)),
				title=_("Invalid Third-Party Shipment"),
			)

		if sales_order.workflow_state == DISPATCHED_STATE:
			return

		if sales_order.workflow_state != "In Transit":
			frappe.throw(
				_(
					"Sales Order {0} must be In Transit before courier details can dispatch it. "
					"Its current state is {1}."
				).format(
					frappe.bold(sales_order.name),
					frappe.bold(sales_order.workflow_state or _("Not Set")),
				),
				title=_("Sales Order Not In Transit"),
			)

		previous_workflow_comment = frappe.db.get_value(
			"Comment",
			{
				"reference_doctype": "Sales Order",
				"reference_name": sales_order.name,
				"comment_type": "Workflow",
			},
			"name",
			order_by="creation desc",
		)
		original_user = frappe.session.user
		try:
			# Remote Users cannot operate Desk workflow actions. This narrowly scoped
			# system transition runs only after server-side shipment validation. Frappe's
			# audit_user records the website user who initiated the elevated action.
			frappe.set_user("Administrator")
			frappe.session.data.audit_user = f"{actor_name} ({actor_user})"
			sales_order.reload()
			available_actions = {
				transition.get("action") for transition in get_transitions(sales_order)
			}
			if COURIER_DETAILS_ACTION not in available_actions:
				frappe.throw(
					_(
						"Workflow action {0} is not available for Sales Order {1} in state {2}."
					).format(
						frappe.bold(COURIER_DETAILS_ACTION),
						frappe.bold(sales_order.name),
						frappe.bold(sales_order.workflow_state),
					),
					title=_("Workflow Transition Unavailable"),
				)

			sales_order = apply_workflow(sales_order, COURIER_DETAILS_ACTION)
			if sales_order.workflow_state != DISPATCHED_STATE:
				frappe.throw(
					_("Sales Order {0} did not reach Dispatched.").format(
						frappe.bold(sales_order.name)
					)
				)
		finally:
			frappe.set_user(original_user)

		workflow_comment = frappe.db.get_value(
			"Comment",
			{
				"reference_doctype": "Sales Order",
				"reference_name": sales_order.name,
				"comment_type": "Workflow",
				"content": DISPATCHED_STATE,
			},
			"name",
			order_by="creation desc",
		)
		if workflow_comment and workflow_comment != previous_workflow_comment:
			frappe.db.set_value(
				"Comment",
				workflow_comment,
				{
					"owner": actor_user,
					"comment_email": actor_user,
					"comment_by": actor_name,
					"modified_by": actor_user,
				},
				update_modified=False,
			)

		frappe.publish_realtime(
			"reload_form",
			{"doctype": "Sales Order", "name": sales_order.name},
			after_commit=True,
		)


def dispatch_sales_order_for_shipment(shipment_name):
	"""Retry the workflow transition for an already-created Web Form response."""
	shipment = frappe.get_doc("Third-Party Shipment", shipment_name)
	if not shipment.courier_details:
		frappe.throw(
			_("Third-Party Shipment {0} has no Courier Details.").format(
				frappe.bold(shipment.name)
			)
		)
	shipment.dispatch_sales_order()
	return frappe.db.get_value("Sales Order", shipment.sales_order, "workflow_state")
