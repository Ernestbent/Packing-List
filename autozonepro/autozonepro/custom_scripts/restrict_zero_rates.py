import frappe
from frappe.utils import flt

def on_submit(doc, method=None):
    """Validate zero rates before submission"""
    check_zero_rates(doc)

def check_zero_rates(doc):
    # Allow this user to submit even with zero rates
    if frappe.session.user == "ernestben69@gmail.com":
        return

    zero_rate_items = []

    for idx, row in enumerate(doc.items, start=1):
        if flt(row.rate) == 0:
            zero_rate_items.append(f"Row {idx}: {row.item_code}")

    if zero_rate_items:
        frappe.throw(
            "Sales Order cannot be submitted with zero rates."
            "<br><br>Items with zero rates:<br>" + "<br>".join(zero_rate_items),
            title="Zero Rate Not Allowed"
        )