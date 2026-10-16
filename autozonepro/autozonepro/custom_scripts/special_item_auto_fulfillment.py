import frappe
from frappe import _
from frappe.utils.synchronization import filelock

from autozonepro.autozonepro.custom_scripts.exclusive_sales_order_item import (
	is_exclusive_item_order,
)


APPROVED_STATE = "Approved"
IN_TRANSIT_STATE = "In Transit"


def on_update_after_submit(doc, method=None):
	"""Queue automatic DN/SI creation after the approval transaction commits."""
	previous_doc = getattr(doc, "_doc_before_save", None)
	previous_state = previous_doc.get("workflow_state") if previous_doc else None
	if (
		doc.workflow_state != APPROVED_STATE
		or previous_state == APPROVED_STATE
		or not is_exclusive_item_order(doc)
	):
		return

	frappe.enqueue(
		"autozonepro.autozonepro.custom_scripts.special_item_auto_fulfillment.process_approved_sales_order",
		queue="long",
		timeout=600,
		enqueue_after_commit=True,
		job_id=f"special-item-auto-fulfillment-{doc.name}",
		deduplicate=True,
		sales_order_name=doc.name,
	)


def process_approved_sales_order(sales_order_name):
	"""Create both submitted documents in one background transaction."""
	lock_name = f"special-item-auto-fulfillment-{frappe.scrub(sales_order_name)}"
	with filelock(lock_name, timeout=10):
		try:
			_process_approved_sales_order(sales_order_name)
		except Exception as error:
			frappe.db.rollback()
			_log_failure(sales_order_name, error)
			frappe.db.commit()
			raise


def _process_approved_sales_order(sales_order_name):
	sales_order = frappe.get_doc("Sales Order", sales_order_name)
	if not is_exclusive_item_order(sales_order):
		return
	if sales_order.workflow_state in {IN_TRANSIT_STATE, "Dispatched", "Delivered"}:
		return
	if sales_order.workflow_state != APPROVED_STATE:
		frappe.throw(
			_(
				"Automatic document creation expected Sales Order {0} to be Approved, "
				"but its current state is {1}."
			).format(
				frappe.bold(sales_order.name),
				frappe.bold(sales_order.workflow_state or _("Not Set")),
			),
			title=_("Automatic Fulfillment Stopped"),
		)

	frappe.flags.in_special_item_auto_fulfillment = True
	try:
		delivery_note = _create_and_submit_delivery_note(sales_order)
		sales_invoice = _create_and_submit_sales_invoice(delivery_note)

		frappe.db.set_value(
			"Sales Order",
			sales_order.name,
			"workflow_state",
			IN_TRANSIT_STATE,
		)
		sales_order.workflow_state = IN_TRANSIT_STATE
		sales_order.add_comment(
			"Comment",
			_(
				"Automatically created Delivery Note {0} and Sales Invoice {1}. "
				"Sales Order moved to In Transit."
			).format(
				frappe.bold(delivery_note.name),
				frappe.bold(sales_invoice.name),
			),
		)
		frappe.publish_realtime(
			"reload_form",
			{"doctype": "Sales Order", "name": sales_order.name},
			after_commit=True,
		)
	finally:
		frappe.flags.in_special_item_auto_fulfillment = False


def _log_failure(sales_order_name, error):
	message = _(
		"Automatic Delivery Note and Sales Invoice creation failed. "
		"The Sales Order remains Approved. Error: {0}"
	).format(str(error))
	if frappe.db.exists("Sales Order", sales_order_name):
		frappe.get_doc("Sales Order", sales_order_name).add_comment("Comment", message)
	frappe.log_error(
		title=f"Automatic fulfillment failed: {sales_order_name}",
		message=frappe.get_traceback(),
	)


def _create_and_submit_delivery_note(sales_order):
	_existing_linked_document(
		child_doctype="Delivery Note Item",
		sales_order_field="against_sales_order",
		sales_order=sales_order.name,
		document_label=_("Delivery Note"),
	)
	_existing_linked_document(
		child_doctype="Sales Invoice Item",
		sales_order_field="sales_order",
		sales_order=sales_order.name,
		document_label=_("Sales Invoice"),
	)

	from erpnext.selling.doctype.sales_order.sales_order import make_delivery_note

	delivery_note = make_delivery_note(sales_order.name)
	if not delivery_note.get("items"):
		frappe.throw(
			_("No quantity remains to create a Delivery Note for Sales Order {0}.").format(
				frappe.bold(sales_order.name)
			),
			title=_("Automatic Delivery Note Failed"),
		)

	delivery_note.flags.ignore_permissions = True
	delivery_note.insert(ignore_permissions=True)
	delivery_note.submit()
	return delivery_note


def _create_and_submit_sales_invoice(delivery_note):
	from erpnext.stock.doctype.delivery_note.delivery_note import make_sales_invoice

	sales_invoice = make_sales_invoice(delivery_note.name)
	if not sales_invoice.get("items"):
		frappe.throw(
			_("No quantity remains to invoice from Delivery Note {0}.").format(
				frappe.bold(delivery_note.name)
			),
			title=_("Automatic Sales Invoice Failed"),
		)

	sales_invoice.flags.ignore_permissions = True
	sales_invoice.insert(ignore_permissions=True)
	sales_invoice.submit()
	return sales_invoice


def _existing_linked_document(
	*, child_doctype, sales_order_field, sales_order, document_label
):
	existing_parent = frappe.db.get_value(
		child_doctype,
		{sales_order_field: sales_order, "docstatus": ["!=", 2]},
		"parent",
	)
	if existing_parent:
		frappe.throw(
			_(
				"Cannot create documents automatically because {0} {1} already exists "
				"for Sales Order {2}. Cancel or complete that document first."
			).format(
				document_label,
				frappe.bold(existing_parent),
				frappe.bold(sales_order),
			),
			title=_("Existing Document Found"),
		)
