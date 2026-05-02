# Copyright (c) 2026, Ernest Benedict and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import cint, flt


class ReturnStock(Document):
    def validate(self):
        self.set_totals()

    def set_totals(self):
        self.total_boxes = sum(cint(row.boxes) for row in (self.table_mwme or []))
        self.total_amount = sum(flt(row.amount) for row in (self.table_mwme or []))


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_sales_person_customers(doctype, txt, searchfield, start, page_len, filters):
    sales_person = (filters or {}).get("sales_person")
    if not sales_person:
        return []

    return frappe.db.sql(
        """
        SELECT DISTINCT c.name, c.customer_name
        FROM `tabCustomer` c
        INNER JOIN `tabSales Team` st
            ON st.parent = c.name
            AND st.parenttype = 'Customer'
            AND st.parentfield = 'sales_team'
        WHERE st.sales_person = %(sales_person)s
            AND c.disabled = 0
            AND (
                c.name LIKE %(txt)s
                OR c.customer_name LIKE %(txt)s
            )
        ORDER BY c.customer_name ASC
        LIMIT %(start)s, %(page_len)s
        """,
        {
            "sales_person": sales_person,
            "txt": f"%{txt}%",
            "start": start,
            "page_len": page_len,
        },
    )
