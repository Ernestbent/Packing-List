import frappe

def on_submit(doc, method):
    """When Sales Invoice submitted → move linked SO to Billed"""
    sales_orders_updated = []

    for item in doc.items:
        if item.sales_order and item.sales_order not in sales_orders_updated:
            so = frappe.get_doc('Sales Order', item.sales_order)
            if so.workflow_state == 'Billing':
                frappe.db.set_value(
                    'Sales Order',
                    item.sales_order,
                    'workflow_state',
                    'Billed'
                )
                frappe.db.commit()
                frappe.publish_realtime('reload_form', {
                    'doctype': 'Sales Order',
                    'name': item.sales_order
                })
                sales_orders_updated.append(item.sales_order)