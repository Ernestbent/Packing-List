import frappe
from frappe import _


EXCLUSIVE_ITEM_CODE = "CE300176PR"
EXCLUSIVE_ITEM_WAREHOUSE = "SHAMBA LOC - APL"


def is_exclusive_item_order(doc):
    items = doc.get("items") or []
    return len(items) == 1 and items[0].get("item_code") == EXCLUSIVE_ITEM_CODE


def validate(doc, method=None):
    """Require the configured item to be alone and supplied from its warehouse."""
    items = doc.get("items") or []
    item_codes = [row.get("item_code") for row in items]

    if EXCLUSIVE_ITEM_CODE not in item_codes:
        return

    if is_exclusive_item_order(doc):
        doc.set_warehouse = EXCLUSIVE_ITEM_WAREHOUSE
        items[0].warehouse = EXCLUSIVE_ITEM_WAREHOUSE
        return

    frappe.throw(
        _(
            "Item {0} must be ordered alone on its own Sales Order. "
            "Remove all other item rows or create a separate Sales Order for this item."
        ).format(frappe.bold(EXCLUSIVE_ITEM_CODE)),
        title=_("Item Must Be Ordered Separately"),
    )
