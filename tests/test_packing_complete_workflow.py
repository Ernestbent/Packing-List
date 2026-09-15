"""Run with bench Python: python -m unittest discover -s tests -p test_packing_complete_workflow.py"""
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

import frappe

from autozonepro.autozonepro.custom_scripts import check_packing_lists as workflow
from autozonepro.autozonepro.doctype.packing_list.packing_list import PackingList


def packing_list(required=10, packed=10, item="A", packed_item="A"):
    doc = PackingList.__new__(PackingList)
    doc.__dict__.update(
        table_ttya=[frappe._dict(item=item, item_name=item, qty=required, uom="Piece")],
        table_hqkk=[frappe._dict(item=packed_item, quantity=packed, box_number=1, uom="Piece")],
        total_qty=999, total_boxes=999,
    )
    return doc


def order(previous="Packing", current="Packed"):
    return SimpleNamespace(doctype="Sales Order", docstatus=1, name="SO-1", workflow_state=current,
                           _doc_before_save=frappe._dict(workflow_state=previous))


class TestPackingCompleteWorkflow(unittest.TestCase):
    def setUp(self):
        self.flags = frappe._dict(mute_messages=False)
        self.records = []
        self.documents = {}
        def throw(message, **kwargs):
            raise frappe.ValidationError(message)
        replacements = [
            patch.object(workflow, "_", side_effect=lambda value: value),
            patch.object(workflow, "get_link_to_form", side_effect=lambda doctype, name: name),
            patch.object(frappe, "flags", self.flags),
            patch.object(frappe, "throw", side_effect=throw),
            patch.object(frappe, "get_all", side_effect=lambda *args, **kwargs: self.records),
            patch.object(frappe, "get_doc", side_effect=lambda doctype, name: self.documents[name]),
        ]
        self.mocks = [replacement.start() for replacement in replacements]
        for replacement in replacements:
            self.addCleanup(replacement.stop)

    def add(self, name="PL-1", status=1, doc=None):
        self.records.append(frappe._dict(name=name, docstatus=status))
        self.documents[name] = doc if doc is not None else packing_list()

    def test_no_linked_list_blocks_transition(self):
        with self.assertRaisesRegex(frappe.ValidationError, "no active Packing List"):
            workflow.before_update_after_submit(order())
        self.mocks[4].assert_called_once_with(
            "Packing List", filters={"custom_sales_order": "SO-1", "docstatus": ["!=", 2]},
            fields=["name", "docstatus"], order_by="creation asc",
        )

    def test_fully_packed_draft_still_blocks_transition(self):
        self.add(status=0)
        with self.assertRaisesRegex(frappe.ValidationError, "not been submitted"):
            workflow.before_update_after_submit(order())

    def test_submitted_but_incomplete_list_blocks_transition(self):
        self.add(doc=packing_list(packed=5))
        with self.assertRaisesRegex(frappe.ValidationError, "PL-1 is not fully"):
            workflow.before_update_after_submit(order())
        self.assertFalse(self.flags.mute_messages)

    def test_submitted_and_fully_packed_list_allows_transition(self):
        self.add()
        workflow.before_update_after_submit(order())
        self.assertEqual(self.documents["PL-1"].total_qty, 10)
        self.assertEqual(self.documents["PL-1"].total_boxes, 1)
        self.assertFalse(self.flags.mute_messages)

    def test_submitted_list_with_wrong_item_blocks_transition(self):
        self.add(doc=packing_list(packed_item="WRONG"))
        with self.assertRaisesRegex(frappe.ValidationError, "not fully and correctly packed"):
            workflow.before_update_after_submit(order())

    def test_overpacked_list_blocks_transition(self):
        self.add(doc=packing_list(packed=11))
        with self.assertRaises(frappe.ValidationError):
            workflow.before_update_after_submit(order())

    def test_empty_submitted_list_blocks_transition(self):
        doc = packing_list()
        doc.table_ttya = []
        doc.table_hqkk = []
        self.add(doc=doc)
        with self.assertRaises(frappe.ValidationError):
            workflow.before_update_after_submit(order())

    def test_one_good_list_does_not_hide_another_unsubmitted_list(self):
        self.add()
        self.add(name="PL-2", status=0)
        with self.assertRaisesRegex(frappe.ValidationError, "PL-2"):
            workflow.before_update_after_submit(order())

    def test_all_submitted_lists_must_be_complete(self):
        self.add()
        self.add(name="PL-2", doc=packing_list(packed=3))
        with self.assertRaisesRegex(frappe.ValidationError, "PL-2"):
            workflow.before_update_after_submit(order())

    def test_duplicate_required_items_are_counted_together(self):
        doc = packing_list(required=5, packed=5)
        doc.table_ttya.append(frappe._dict(item="A", item_name="A", qty=5, uom="Piece"))
        self.add(doc=doc)
        with self.assertRaises(frappe.ValidationError):
            workflow.before_update_after_submit(order())

    def test_unrelated_workflow_actions_and_saves_are_unaffected(self):
        for previous, current in [("Packed", "Billing"), ("Packing", "Packing"), ("Approved", "Picking")]:
            workflow.before_update_after_submit(order(previous, current))
        self.mocks[4].assert_not_called()

    def test_start_packing_keeps_existing_pick_list_check(self):
        with self.assertRaisesRegex(frappe.ValidationError, "no Pick List linked"):
            workflow.before_update_after_submit(order("Picking", "Packing"))

    def test_unexpected_validation_error_is_not_silenced(self):
        doc = packing_list()
        doc.validate_packaging_complete = Mock(side_effect=RuntimeError("unexpected"))
        self.add(doc=doc)
        with self.assertRaisesRegex(RuntimeError, "unexpected"):
            workflow.before_update_after_submit(order())
        self.assertFalse(self.flags.mute_messages)
