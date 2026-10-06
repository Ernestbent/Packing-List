import unittest
from unittest.mock import Mock, patch

import frappe

from autozonepro.autozonepro.custom_scripts import payment_entry_hooks


get_reference_digits = payment_entry_hooks.get_reference_digits
validate_unique_reference_no_for_restricted_modes = (
	payment_entry_hooks.validate_unique_reference_no_for_restricted_modes
)


class TestPaymentEntryHooks(unittest.TestCase):
	def test_reference_digits_ignore_formatting(self):
		for reference_no in ("567", "567.", " 5-6/7 ", "REF 567"):
			with self.subTest(reference_no=reference_no):
				self.assertEqual(get_reference_digits(reference_no), "567")

	def test_reference_without_digits_has_empty_digit_value(self):
		self.assertEqual(get_reference_digits("REFERENCE"), "")

	def test_matching_digits_are_rejected(self):
		database = Mock()
		database.multisql.return_value = [
			frappe._dict(name="ACC-PAY-2026-00001", mode_of_payment="Bank", reference_no="567.")
		]
		doc = frappe._dict(
			name="ACC-PAY-2026-00002",
			mode_of_payment="Bank",
			reference_no="567",
		)

		with (
			patch.dict(payment_entry_hooks.frappe.__dict__, {"db": database}),
			patch.object(payment_entry_hooks.frappe, "throw", side_effect=frappe.ValidationError),
			self.assertRaises(frappe.ValidationError),
		):
			validate_unique_reference_no_for_restricted_modes(doc)

		self.assertEqual(database.multisql.call_args.args[1], ("567", "567", "567", doc.name))

	def test_unrestricted_mode_is_not_checked(self):
		database = Mock()
		doc = frappe._dict(name="ACC-PAY-2026-00002", mode_of_payment="Cash", reference_no="567.")

		with patch.dict(payment_entry_hooks.frappe.__dict__, {"db": database}):
			validate_unique_reference_no_for_restricted_modes(doc)

		database.multisql.assert_not_called()


if __name__ == "__main__":
	unittest.main()
