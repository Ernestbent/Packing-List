import frappe
from frappe import _

from erpnext.selling.doctype.customer.customer import Customer


class CustomCustomer(Customer):
	def validate_credit_limit_on_change(self):
		"""Allow lowering credit limit below current outstanding amount."""
		if self.get("__islocal") or not self.credit_limits:
			return

		past_credit_limits = [
			d.credit_limit
			for d in frappe.db.get_all(
				"Customer Credit Limit",
				filters={"parent": self.name},
				fields=["credit_limit"],
				order_by="company",
			)
		]

		current_credit_limits = [d.credit_limit for d in sorted(self.credit_limits, key=lambda k: k.company)]

		if past_credit_limits == current_credit_limits:
			return

		company_record = []
		for limit in self.credit_limits:
			if limit.company in company_record:
				frappe.throw(
					_("Credit limit is already defined for the Company {0}").format(limit.company, self.name)
				)
			company_record.append(limit.company)
