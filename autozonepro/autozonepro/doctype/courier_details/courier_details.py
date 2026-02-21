# Copyright (c) 2026, Ernest Benedict and contributors
# For license information, please see license.txt

from frappe.model.document import Document


class CourierDetails(Document):

    def validate(self):
        self.full_name = self.get_full_name()

    def get_full_name(self):
        first_name = self.first_name 
        surname = self.surname 
        return f"{first_name} {surname}".strip()
