# Copyright (c) 2026, Ernest Benedict and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt


class CashItems(Document):
	def validate(self):
		seen_items = set()

		for row in self.items:
			if flt(row.quantity) <= 0:
				frappe.throw(_("Row {0}: Quantity must be greater than zero.").format(row.idx))

			if row.item in seen_items:
				frappe.throw(_("Row {0}: Item {1} is listed more than once.").format(row.idx, row.item))

			seen_items.add(row.item)
