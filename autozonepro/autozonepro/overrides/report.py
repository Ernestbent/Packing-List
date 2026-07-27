from frappe.core.doctype.report.report import Report

from autozonepro.autozonepro.utils.report_settings import is_prepared_report_disabled


class AutozoneproReport(Report):
	"""Prevent selected reports from being automatically made prepared reports."""

	def execute_script_report(self, filters):
		if not is_prepared_report_disabled(self.name):
			return super().execute_script_report(filters)

		# Frappe starts a 15-second timer only when this value is false. Set it
		# in memory while the report runs so the timer cannot update the database.
		prepared_report = self.prepared_report
		self.prepared_report = 1

		try:
			return super().execute_script_report(filters)
		finally:
			self.prepared_report = prepared_report
