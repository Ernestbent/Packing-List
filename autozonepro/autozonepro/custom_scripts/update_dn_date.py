import frappe
from frappe import _

@frappe.whitelist()
def update_delivery_date(sales_order, delivery_date):
    """Update the Received Date in linked Delivery Notes for the given Sales Order"""
    
    # Log for debugging
    frappe.log_error(f"update_delivery_date called with sales_order: {sales_order}, delivery_date: {delivery_date}")
    
    # Validate delivery_date
    try:
        frappe.utils.getdate(delivery_date)  # Parse and validate date
    except ValueError:
        frappe.throw(_("Received Date must be a valid date"))
    
    # Check if custom_delivery_date field exists
    if not frappe.get_meta("Delivery Note").has_field("custom_delivery_date"):
        frappe.throw(_("Custom field 'custom_delivery_date' (Received Date) not found in Delivery Note"))
    
    # Get distinct Delivery Notes linked to the Sales Order
    delivery_notes = frappe.get_all(
        "Delivery Note Item",
        filters={"against_sales_order": sales_order},
        fields=["distinct parent"]
    )
    
    # Handle case where no Delivery Notes are found
    if not delivery_notes:
        frappe.log_error(f"No Delivery Notes found for Sales Order {sales_order}")
        return []
    
    updated = []
    
    try:
        for dn_item in delivery_notes:
            frappe.db.set_value("Delivery Note", dn_item.parent, "custom_delivery_date", delivery_date)
            updated.append(dn_item.parent)
        
        frappe.db.commit()  # Explicit commit to ensure changes are saved
        
    except Exception as e:
        frappe.db.rollback()
        frappe.log_error(f"Error updating Delivery Notes for Sales Order {sales_order}: {str(e)}")
        frappe.throw(_("Failed to update Delivery Notes: {0}").format(str(e)))
    
    return updated