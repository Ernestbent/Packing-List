# Copyright (c) 2026, Ernest Benedict and contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase

from autozonepro.autozonepro.doctype.dispatch_register.dispatch_register import (
	bundle_expenses,
)


class TestDispatchRegister(FrappeTestCase):
	def test_bundle_expenses_preserve_total(self):
		expenses = bundle_expenses(100, 3)

		self.assertEqual(expenses, [33.33, 33.33, 33.34])
		self.assertEqual(sum(expenses), 100)

	def test_bundle_expenses_reject_non_positive_count(self):
		self.assertEqual(bundle_expenses(100, 0), [])

	def test_register_calculates_row_and_parent_totals(self):
		register = frappe.get_doc(
			{
				"doctype": "Dispatch Register",
				"rows": [
					{
						"delivery_note": "DN-TEST-1",
						"driver_name": "Test Driver",
						"vehicle_number": "UBA 123A",
						"telephone": "+256700000000",
						"number_of_bundles": 4,
						"total_expense": 48000,
					},
					{
						"delivery_note": "DN-TEST-2",
						"driver_name": "Test Driver",
						"vehicle_number": "UBA 123A",
						"telephone": "+256700000000",
						"number_of_bundles": 6,
						"total_expense": 60000,
					},
				],
			}
		)

		for row in register.rows:
			row.cost_per_bundle = row.total_expense / row.number_of_bundles
		register._set_totals()

		self.assertEqual(register.total_bundles, 10)
		self.assertEqual(register.total_expense, 108000)
		self.assertEqual(register.rows[0].cost_per_bundle, 12000)
		self.assertEqual(register.rows[1].cost_per_bundle, 10000)
