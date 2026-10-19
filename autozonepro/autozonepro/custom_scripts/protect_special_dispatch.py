import frappe
from frappe import _

from autozonepro.autozonepro.custom_scripts.exclusive_sales_order_item import (
	EXCLUSIVE_ITEM_CODE,
	is_exclusive_item_order,
)


PROTECTED_TRANSITIONS = {
	("In Transit", "Being Delivered"),
	("In Transit", "Dispatched"),
	("Being Delivered", "Dispatched"),
}


def validate(doc, method=None):
	"""Allow special orders to dispatch only through validated courier submission."""
	if not is_exclusive_item_order(doc):
		return

	previous_doc = doc.get_doc_before_save()
	if not previous_doc:
		return

	transition = (previous_doc.workflow_state, doc.workflow_state)
	if transition not in PROTECTED_TRANSITIONS:
		return

	if getattr(frappe.flags, "in_validated_courier_dispatch", False):
		return

	frappe.throw(
		_(
			"Sales Order {0} contains item {1} and cannot be marked as dispatched directly. "
			"Submit its courier details through the Dispatch Register instead."
		).format(frappe.bold(doc.name), frappe.bold(EXCLUSIVE_ITEM_CODE)),
		title=_("Use Dispatch Register"),
	)
