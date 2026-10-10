import frappe
from frappe.core.doctype.report.report import Report
from frappe.utils import cint


class SynchronousReport(Report):
	"""Keep Script Reports synchronous when enabled for the current site."""

	def execute_script_report(self, filters):
		if not cint(frappe.conf.get("autozonepro_force_synchronous_reports")):
			return super().execute_script_report(filters)

		# Frappe starts a timer that permanently marks a report as prepared when
		# execution exceeds 15 seconds. Marking this in-memory document as prepared
		# skips only that timer; query_report.run is still executing it synchronously.
		was_prepared_report = self.prepared_report
		self.prepared_report = 1
		try:
			return super().execute_script_report(filters)
		finally:
			self.prepared_report = was_prepared_report
