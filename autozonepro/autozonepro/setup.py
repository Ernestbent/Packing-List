import frappe

from autozonepro.autozonepro.custom_scripts.remote_shipment_whatsapp import setup_custom_fields
from autozonepro.autozonepro.custom_scripts.special_item_workflow import (
	configure_special_item_workflow,
)


def after_migrate():
	configure_special_item_workflow()
	setup_custom_fields()
	configure_third_party_shipment_web_form()


def configure_third_party_shipment_web_form():
	"""Always allow a Remote User to open a new shipment from a Delivery Note link."""
	if frappe.db.exists("Web Form", "third-party-shipment"):
		frappe.db.set_value(
			"Web Form",
			"third-party-shipment",
			"allow_multiple",
			1,
			update_modified=False,
		)
