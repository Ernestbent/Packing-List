# Run without a database: python -m unittest autozonepro.autozonepro.doctype.packing_list.test_packing_list
import unittest
from unittest.mock import patch

import frappe

from autozonepro.autozonepro.doctype.packing_list.packing_list import PackingList


def item(qty, code="A", uom="Nos"):
    return frappe._dict(item=code, item_name=code, qty=qty, uom=uom)


def packed(qty, box=1, code="A", **kwargs):
    return frappe._dict(item=code, quantity=qty, box_number=box, uom="Nos", **kwargs)


class TestPackingList(unittest.TestCase):
    def make_doc(self, items, boxes):
        # Exercise the real controller without requiring site metadata or DB writes.
        doc = PackingList.__new__(PackingList)
        doc.__dict__.update(table_ttya=items, table_hqkk=boxes)
        return doc

    def setUp(self):
        def throw(message, **kwargs):
            raise frappe.ValidationError(message)

        self.throw_patch = patch("frappe.throw", side_effect=throw)
        self.throw_patch.start()
        self.addCleanup(self.throw_patch.stop)

    def test_duplicate_lines_require_combined_quantity(self):
        doc = self.make_doc([item(5), item(5)], [packed(5)])
        doc.validate()  # Partial packing is a valid draft.
        missing = doc.get_missing_or_invalid_packed_items()
        self.assertEqual(missing[0]["required_qty"], 10)
        self.assertEqual(missing[0]["packed_qty"], 5)
        with self.assertRaises(frappe.ValidationError):
            doc.validate_packaging_complete()
        doc.table_hqkk.append(packed(5, box=2))
        doc.validate()
        doc.validate_packaging_complete()
        self.assertEqual(doc.total_qty, 10)
        self.assertEqual(doc.total_boxes, 2)

    def test_mixed_legacy_and_indexed_rows_are_counted(self):
        doc = self.make_doc([item(10)], [packed(4), packed(6, box=2, source_row_idx=0)])
        doc.validate()
        doc.validate_packaging_complete()
        doc.table_hqkk.append(packed(4, box=3))
        with self.assertRaises(frappe.ValidationError):
            doc.validate()

    def test_matching_index_cannot_substitute_the_wrong_item(self):
        doc = self.make_doc([item(10, code="B")], [packed(10, source_row_idx=0)])
        with self.assertRaises(frappe.ValidationError):
            doc.validate()

    def test_reordering_source_rows_does_not_change_packed_identity(self):
        doc = self.make_doc(
            [item(3, code="B"), item(5)],
            [packed(5, source_row_idx=0), packed(3, box=2, code="B", source_row_idx=1)],
        )
        doc.validate()
        doc.validate_packaging_complete()

    def test_same_item_in_different_uoms_is_not_combined(self):
        doc = self.make_doc([item(5), item(2, uom="Box")], [packed(7)])
        with self.assertRaises(frappe.ValidationError):
            doc.validate()
        doc.table_hqkk = [packed(5), frappe._dict(item="A", quantity=2, box_number=2, uom="Box")]
        doc.validate()
        doc.validate_packaging_complete()

    def test_extra_items_are_rejected_even_when_required_items_are_complete(self):
        doc = self.make_doc([item(5)], [packed(5), packed(1, box=2, code="EXTRA")])
        with self.assertRaises(frappe.ValidationError):
            doc.validate()

    def test_invalid_quantities_are_rejected(self):
        for qty in (0, -1, 1.5, float("inf"), float("nan")):
            with self.subTest(qty=qty):
                doc = self.make_doc([item(5)], [packed(qty)])
                with self.assertRaises(frappe.ValidationError):
                    doc.validate()

    def test_invalid_box_numbers_are_rejected(self):
        for box in (0, -1, 1.5):
            with self.subTest(box=box):
                doc = self.make_doc([item(5)], [packed(5, box=box)])
                with self.assertRaises(frappe.ValidationError):
                    doc.validate()

    def test_empty_draft_cannot_be_submitted(self):
        doc = self.make_doc([], [])
        doc.validate()
        with self.assertRaises(frappe.ValidationError):
            doc.validate_packaging_complete()
