"""Run with the bench Python: python -m unittest discover -s tests -p test_workflow_stock.py"""
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

import frappe
from autozonepro.autozonepro.custom_scripts import sales_order_pick_list_stock as stock


class Doc(SimpleNamespace):
    def get(self, key):
        return getattr(self, key, None)


def order_row(qty, code="A", conversion=1, **extra):
    return frappe._dict(item_code=code, item_name=code, qty=qty, conversion_factor=conversion,
                        uom="Box" if conversion != 1 else "Piece", stock_uom="Piece", **extra)


class TestWorkflowStock(unittest.TestCase):
    def setUp(self):
        self.translations = patch.object(stock, "_", side_effect=lambda value: value)
        self.translations.start()
        self.addCleanup(self.translations.stop)

    def doc(self, items, previous="Approved", current="Picking"):
        return Doc(doctype="Sales Order", docstatus=1, company="Autozone Parts Limited", items=items,
                   workflow_state=current, _doc_before_save=frappe._dict(workflow_state=previous))

    def check(self, doc, main=0, container_1=1000, container_2=0):
        quantities = {"A": {"main_qty": main, "container_qty": container_1 + container_2,
                            "container_1_qty": container_1, "container_2_qty": container_2}}
        def throw(message, **kwargs):
            raise frappe.ValidationError(message)
        with patch.object(stock, "get_pick_list_stock_by_item", return_value=quantities) as lookup, \
             patch.object(frappe, "throw", side_effect=throw) as thrown:
            try:
                stock.before_update_after_submit(doc)
            except frappe.ValidationError:
                pass
        return lookup, thrown

    def test_create_pick_list_transition_rejects_shortage(self):
        doc = self.doc([order_row(10)])
        lookup, thrown = self.check(doc)
        self.assertTrue(lookup.called)
        self.assertTrue(thrown.called)
        self.assertEqual(thrown.call_args.kwargs["title"], "Stock Shortfall in Main Location")
        self.assertTrue(thrown.call_args.kwargs["wide"])
        self.assertIn("<table", thrown.call_args.args[0])
        self.assertEqual(doc._doc_before_save.workflow_state, "Approved")

    def test_live_stock_overrides_stale_order_values(self):
        _, thrown = self.check(self.doc([order_row(10, actual_qty=100, containers=0)]))
        self.assertTrue(thrown.called)
        _, thrown = self.check(self.doc([order_row(10, actual_qty=0, containers=1000)]), main=10)
        self.assertFalse(thrown.called)

    def test_duplicate_items_are_combined(self):
        _, thrown = self.check(self.doc([order_row(6), order_row(6)]), main=10)
        self.assertTrue(thrown.called)
        args = thrown.call_args.kwargs["primary_action"]["args"]
        self.assertEqual(len(args["items"]), 1)
        self.assertEqual(args["items"][0]["qty"], 2)

    def test_order_uom_is_converted_to_stock_uom(self):
        _, thrown = self.check(self.doc([order_row(2, conversion=10)]), main=5)
        transfer = thrown.call_args.kwargs["primary_action"]["args"]["items"][0]
        self.assertEqual(transfer["qty"], 15)
        self.assertEqual(transfer["uom"], "Piece")
        self.assertEqual(transfer["conversion_factor"], 1)

    def test_unrelated_workflow_changes_and_normal_saves_are_unaffected(self):
        for previous, current in [("Picking", "Picking"), ("Picking", "Packing"), ("Approved", "Approved")]:
            with self.subTest(previous=previous, current=current):
                lookup, thrown = self.check(self.doc([order_row(10)], previous, current))
                self.assertFalse(lookup.called)
                self.assertFalse(thrown.called)

    def test_no_container_stock_preserves_original_rule(self):
        _, thrown = self.check(self.doc([order_row(10)]), container_1=0)
        self.assertFalse(thrown.called)

    def test_transfer_splits_shortage_across_containers(self):
        _, thrown = self.check(self.doc([order_row(10)]), main=1, container_1=5, container_2=4)
        transfers = thrown.call_args.kwargs["primary_action"]["args"]["items"]
        self.assertEqual([item["qty"] for item in transfers], [5, 4])
        self.assertEqual([item["s_warehouse"] for item in transfers], list(stock.CONTAINER_WAREHOUSES))
        self.assertTrue(all(item["t_warehouse"] == stock.MAIN_LOCATION_WAREHOUSE for item in transfers))

    def test_transfer_does_not_exceed_stock_in_either_container(self):
        _, thrown = self.check(self.doc([order_row(10)]), container_1=2, container_2=3)
        transfers = thrown.call_args.kwargs["primary_action"]["args"]["items"]
        self.assertEqual([item["qty"] for item in transfers], [3, 2])

    def test_dialog_escapes_item_content(self):
        row = order_row(10)
        row.item_name = '<img src=x onerror=alert(1)>'
        _, thrown = self.check(self.doc([row]))
        self.assertNotIn('<img', thrown.call_args.args[0])
        self.assertIn('&lt;img', thrown.call_args.args[0])

    def test_stock_query_returns_both_container_totals(self):
        row = frappe._dict(item_code="A", main_qty=1, container_qty=7, container_1_qty=3, container_2_qty=4)
        db = Mock()
        db.sql.return_value = [row]
        with patch.object(frappe, "db", db):
            result = stock.get_pick_list_stock_by_item(["A"])
        self.assertEqual(result["A"]["container_1_qty"], 3)
        self.assertEqual(result["A"]["container_2_qty"], 4)
        self.assertEqual(result["A"]["container_qty"], 7)
