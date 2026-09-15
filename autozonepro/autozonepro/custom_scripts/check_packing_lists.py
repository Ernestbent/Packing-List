import frappe
from frappe import _
from frappe.utils import get_link_to_form


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

    if previous_state == "Picking" and current_state == "Packing":
        blocked_message = get_start_packing_block_message(doc.name)
        if blocked_message:
            frappe.throw(blocked_message, title=_("Start Packing Blocked"))
    elif previous_state == "Packing" and current_state == "Packed":
        validate_packing_complete(doc.name)


def validate_packing_complete(sales_order):
    """Recheck saved Packing Lists before accepting Packing Complete."""
    packing_lists = frappe.get_all(
        "Packing List",
        filters={"custom_sales_order": sales_order, "docstatus": ["!=", 2]},
        fields=["name", "docstatus"],
        order_by="creation asc",
    )
    title = _("Packing Complete Blocked")
    if not packing_lists:
        frappe.throw(
            _("Cannot complete packing: no active Packing List is linked to this Sales Order. "
              "Create a Packing List, pack all items and submit it first."),
            title=title,
        )

    drafts = [row.name for row in packing_lists if row.docstatus != 1]
    if drafts:
        frappe.throw(
            _("Cannot complete packing: the following Packing Lists have not been submitted: {0}. "
              "Pack all items and submit these lists first.").format(
                ", ".join(get_link_to_form("Packing List", name) for name in drafts)
            ),
            title=title,
        )

    for row in packing_lists:
        packing_list = frappe.get_doc("Packing List", row.name)
        # Recalculate from saved rows; submitted status/header totals alone are not proof.
        validation_error = None
        previous_mute = frappe.flags.mute_messages
        try:
            frappe.flags.mute_messages = True
            packing_list.set_packaging_totals()
            packing_list.validate_packaging_complete()
        except frappe.ValidationError as error:
            validation_error = str(error)
        finally:
            frappe.flags.mute_messages = previous_mute

        if validation_error is not None:
            frappe.throw(
                _("Cannot complete packing: Packing List {0} is not fully and correctly packed.")
                .format(get_link_to_form("Packing List", row.name))
                + "<br><br>" + validation_error,
                title=title,
            )


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
