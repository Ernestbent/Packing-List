import frappe
from frappe import _

from autozonepro.autozonepro.custom_scripts.exclusive_sales_order_item import (
    is_exclusive_item_order,
)


def _has_submitted_delivery_note(sales_order):
    return bool(
        frappe.db.exists(
            "Delivery Note Item",
            {"against_sales_order": sales_order, "docstatus": 1},
        )
    )


def on_submit(doc, method):
    """Move normal orders to Billed and special tyre orders directly to In Transit."""
    sales_orders_updated = []

    for item in doc.items:
        if item.sales_order and item.sales_order not in sales_orders_updated:
            so = frappe.get_doc('Sales Order', item.sales_order)
            if so.workflow_state == 'Billing':
                next_state = 'Billed'

                if is_exclusive_item_order(so):
                    if not _has_submitted_delivery_note(so.name):
                        frappe.throw(
                            _(
                                "Submit the Delivery Note for Sales Order {0} before submitting its Sales Invoice."
                            ).format(frappe.bold(so.name)),
                            title=_("Submitted Delivery Note Required"),
                        )
                    next_state = 'In Transit'

                frappe.db.set_value(
                    'Sales Order',
                    item.sales_order,
                    'workflow_state',
                    next_state
                )
                frappe.publish_realtime('reload_form', {
                    'doctype': 'Sales Order',
                    'name': item.sales_order
                })
                sales_orders_updated.append(item.sales_order)
