import frappe
from frappe.model.document import Document
from frappe.utils import flt

class PackingList(Document):
    def validate(self):
        self.set_packaging_totals()

    def before_submit(self):
        self.set_packaging_totals()
        self.validate_packaging_complete()
        self.validate_packer()
        self.validate_camera()

    def validate_packer(self):
        if not self.custom_packer or self.custom_packer == 'Select':
            frappe.throw("Please select a Packer before submitting.")

    def validate_camera(self):
        if not self.custom_camera_number or self.custom_camera_number == 'Select':
            frappe.throw("Please select a Camera Number before submitting.")

    def set_packaging_totals(self):
        packed_rows = self.get("table_hqkk") or []
        box_numbers = {
            row.box_number
            for row in packed_rows
            if row.box_number and flt(row.quantity) > 0
        }

        self.total_boxes = len(box_numbers)
        self.total_qty = sum(flt(row.quantity) for row in packed_rows)

    def validate_packaging_complete(self):
        if not self.get("table_ttya"):
            frappe.throw(
                "Cannot submit Packing List without any items.",
                title="No Items Found",
            )

        if not self.get("table_hqkk"):
            frappe.throw(
                "Cannot submit Packing List without any boxes.",
                title="No Boxes Found",
            )

        if not self.total_boxes:
            frappe.throw(
                "Cannot submit Packing List without any valid boxes.",
                title="No Boxes Found",
            )

        missing_or_invalid_items = self.get_missing_or_invalid_packed_items()

        if missing_or_invalid_items:
            message = "<br>".join(
                "{0}: Required <b>{1:g}</b>, Packed <b>{2:g}</b>".format(
                    item["item_name"],
                    item["required_qty"],
                    item["packed_qty"],
                )
                for item in missing_or_invalid_items
            )

            frappe.throw(
                "Cannot submit Packing List because some items are not fully packed:"
                "<br><br>{0}".format(message),
                title="Packing Incomplete",
            )

    def get_missing_or_invalid_packed_items(self):
        items = self.get("table_ttya") or []
        packed_rows = self.get("table_hqkk") or []

        if not items:
            return []

        has_source_row_idx = any(row.get("source_row_idx") not in (None, "") for row in packed_rows)

        if has_source_row_idx:
            return self.get_missing_or_invalid_items_by_source_row(items, packed_rows)

        return self.get_missing_or_invalid_items_by_item_code(items, packed_rows)

    def get_missing_or_invalid_items_by_source_row(self, items, packed_rows):
        packed_by_row = {}

        for row in packed_rows:
            source_row_idx = row.get("source_row_idx")
            if source_row_idx in (None, ""):
                continue

            source_row_idx = int(source_row_idx)
            packed_by_row[source_row_idx] = packed_by_row.get(source_row_idx, 0) + flt(row.quantity)

        missing_or_invalid_items = []
        for idx, item in enumerate(items):
            required_qty = flt(item.qty)
            packed_qty = flt(packed_by_row.get(idx))

            if packed_qty != required_qty:
                missing_or_invalid_items.append(
                    {
                        "item_name": item.item_name or item.item,
                        "required_qty": required_qty,
                        "packed_qty": packed_qty,
                    }
                )

        return missing_or_invalid_items

    def get_missing_or_invalid_items_by_item_code(self, items, packed_rows):
        required_by_item = {}
        packed_by_item = {}
        item_labels = {}

        for item in items:
            required_by_item[item.item] = required_by_item.get(item.item, 0) + flt(item.qty)
            item_labels[item.item] = item.item_name or item.item

        for row in packed_rows:
            packed_by_item[row.item] = packed_by_item.get(row.item, 0) + flt(row.quantity)

        missing_or_invalid_items = []
        for item_code, required_qty in required_by_item.items():
            packed_qty = flt(packed_by_item.get(item_code))

            if packed_qty != required_qty:
                missing_or_invalid_items.append(
                    {
                        "item_name": item_labels.get(item_code) or item_code,
                        "required_qty": required_qty,
                        "packed_qty": packed_qty,
                    }
                )

        return missing_or_invalid_items

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
