import frappe

def before_submit(doc, method):
    """Block submission if Picker is not selected"""
    if not doc.custom_picker or doc.custom_picker == 'Select':
        frappe.throw(
            "Please select a Picker before submitting."
        )