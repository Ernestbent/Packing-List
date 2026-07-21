import frappe
from frappe import _


@frappe.whitelist()
def validate_packing_list_verified(sales_order):
    """Ensure Start Packing has a linked Pick List."""

    blocked_message = get_start_packing_block_message(sales_order)
    if blocked_message:
        return {"blocked": True, "message": blocked_message}

    return {"blocked": False}


def before_update_after_submit(doc, method=None):
    if doc.doctype != "Sales Order" or doc.docstatus != 1:
        return

    previous_doc = getattr(doc, "_doc_before_save", None)
    previous_state = previous_doc.workflow_state if previous_doc else None
    current_state = doc.workflow_state

    if previous_state != "Picking" or current_state != "Packing":
        return

    blocked_message = get_start_packing_block_message(doc.name)
    if blocked_message:
        frappe.throw(blocked_message, title=_("Start Packing Blocked"))


def get_start_packing_block_message(sales_order):
    if not has_linked_pick_list(sales_order):
        return _(
            "Cannot start packing because there is no Pick List linked to this Sales Order in Connections."
        )

    return None


def has_linked_pick_list(sales_order):
    return bool(
        frappe.get_all(
            "Pick List",
            filters=[
                ["Pick List Item", "sales_order", "=", sales_order],
                ["docstatus", "!=", 2],
            ],
            fields=["name"],
            limit=1,
        )
    )
