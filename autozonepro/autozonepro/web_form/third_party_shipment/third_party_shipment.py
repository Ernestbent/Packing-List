import frappe
from frappe import _


def get_context(context):
	# Keep this operational form heading short; the global website title prefix
	# makes it unnecessarily long on small screens.
	return {
		"title": _("Tyre Delivery Handover"),
		"title_prefix": "",
	}


@frappe.whitelist()
def get_delivery_note_customer(delivery_note):
	if frappe.session.user == "Guest":
		frappe.throw(_("Please log in to view this shipment."), frappe.AuthenticationError)

	allowed_roles = {"Remote User", "System Manager"}
	if not allowed_roles.intersection(frappe.get_roles()):
		frappe.throw(_("You are not permitted to view this shipment."), frappe.PermissionError)

	customer = frappe.db.get_value(
		"Delivery Note",
		{"name": delivery_note, "docstatus": 1},
		"customer",
	)
	if not customer:
		frappe.throw(_("Submitted Delivery Note {0} was not found.").format(delivery_note))

	existing_shipment = frappe.db.get_value(
		"Third-Party Shipment",
		{"delivery_note": delivery_note},
		"name",
	)

	return {
		"customer": customer,
		"already_submitted": bool(existing_shipment),
	}
