import frappe
from frappe.model.document import Document

class PackingList(Document):
    def before_submit(self):
        self.validate_packer()
        self.validate_camera()
        self.validate_packaging_verified()

    def validate_packer(self):
        if not self.custom_packer or self.custom_packer == 'Select':
            frappe.throw("Please select a Packer before submitting.")

    def validate_camera(self):
        if not self.custom_camera_number or self.custom_camera_number == 'Select':
            frappe.throw("Please select a Camera Number before submitting.")

    def validate_packaging_verified(self):
        if not self.table_hqkk:
            frappe.throw(
                "Please add Packaging Details before submitting."
            )

        unverified = [
            row.idx for row in self.table_hqkk
            if not row.verifier_2
        ]

        if unverified:
            rows = ", ".join(str(r) for r in unverified)
            frappe.throw(
                f"Please verify all rows before submitting.<br><br>"
                f"Unverified row(s): <b>{rows}</b>"
            )

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
                frappe.publish_realtime('reload_form', {
                    'doctype': 'Sales Order',
                    'name': self.custom_sales_order
                })