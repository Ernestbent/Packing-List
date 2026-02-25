import frappe
from frappe.model.document import Document

class PackingList(Document):
    def before_submit(self):
        self.validate_packer()
        self.validate_camera()

    def validate_packer(self):
        if not self.custom_packer or self.custom_packer == 'Select':
            frappe.throw("Please select a Packer before submitting.")

    def validate_camera(self):
        if not self.custom_camera_number or self.custom_camera_number == 'Select':
            frappe.throw("Please select a Camera Number before submitting.")

    def on_submit(self):
        if self.custom_sales_order:
            so = frappe.get_doc('Sales Order', self.custom_sales_order)
            if so.workflow_state == 'Packing':
                frappe.db.set_value(
                    'Sales Order',
                    self.custom_sales_order,
                    'workflow_state',
                    'Packed'
                )
                frappe.db.commit()