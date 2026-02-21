import frappe
from frappe import _

@frappe.whitelist()
def validate_packing_list_verified(sales_order):
    """Ensure all Packing Lists linked to Sales Order are Verified"""

    packing_lists = frappe.get_all(
        "Packing List",
        filters={"custom_sales_order": sales_order},
        fields=["name", "workflow_state"]
    )

    if not packing_lists:
        # return message instead of throwing
        return {"blocked": True, "message": _("No Packing List found for this Sales Order")}

    not_verified = [
        pl.name for pl in packing_lists
        if pl.workflow_state != "Verified"
    ]

    if not_verified:
        links = ", ".join([f"<a href='/app/packing-list/{pl}' target='_blank'>{pl}</a>" for pl in not_verified])
        return {"blocked": True, "message": _("Cannot start packing. These Packing Lists are not Verified:<br>{0}").format(links)}

    # Everything verified, allow workflow
    return {"blocked": False}
