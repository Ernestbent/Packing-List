from math import isfinite

import frappe
from frappe.model.document import Document
from frappe.utils import escape_html, flt


class PackingList(Document):
    def validate(self):
        self.validate_packed_quantities()
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
        self.validate_packed_quantities()
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
                    escape_html(item["item_name"]),
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

    @staticmethod
    def packing_item_key(row):
        # These fields survive reloads; array positions and source_row_idx do not.
        return (row.item or "", row.uom or "")

    def get_packing_quantities(self):
        required = {}
        packed = {}
        labels = {}
        for row in self.get("table_ttya") or []:
            key = self.packing_item_key(row)
            required[key] = required.get(key, 0) + flt(row.qty)
            labels[key] = row.item_name or row.item
        for row in self.get("table_hqkk") or []:
            key = self.packing_item_key(row)
            packed[key] = packed.get(key, 0) + flt(row.quantity)
            labels.setdefault(key, row.item)
        return required, packed, labels

    def validate_packed_quantities(self):
        # Drafts may be partially packed, but may never contain invalid/extra stock.
        for row in self.get("table_hqkk") or []:
            qty = flt(row.quantity)
            box = flt(row.box_number)
            if not isfinite(qty) or qty <= 0 or not qty.is_integer():
                frappe.throw("Packed quantities must be positive whole numbers.")
            if not isfinite(box) or box <= 0 or not box.is_integer():
                frappe.throw("Box numbers must be positive whole numbers.")

        required, packed, labels = self.get_packing_quantities()
        for key, qty in packed.items():
            if key not in required:
                frappe.throw(
                    "Packed item {0} ({1}) is not in the items to pack.".format(
                        escape_html(key[0]), escape_html(key[1])
                    )
                )
            if qty > required[key]:
                frappe.throw(
                    "Cannot pack {0:g} units of {1} ({2}). Only {3:g} required.".format(
                        qty, escape_html(labels[key]), escape_html(key[1]), required[key]
                    )
                )

    def get_missing_or_invalid_packed_items(self):
        required, packed, labels = self.get_packing_quantities()
        return [
            {
                "item_name": "{0} ({1})".format(labels[key], key[1]) if key[1] else labels[key],
                "required_qty": required.get(key, 0),
                "packed_qty": packed.get(key, 0),
            }
            for key in dict.fromkeys([*required, *packed])
            if packed.get(key, 0) != required.get(key, 0)
        ]

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
