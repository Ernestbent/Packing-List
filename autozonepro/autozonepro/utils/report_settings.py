import frappe
from frappe import _

REPORTS_WITH_PREPARED_REPORT_DISABLED = (
	"General Ledger",
	"Trial Balance",
	"Accounts Receivable",
	"Accounts Payable",
	"Balance Sheet",
	"Profit and Loss Statement",
	"Stock Ledger",
	"Stock Balance",
)


def is_prepared_report_disabled(report_name: str) -> bool:
	return report_name in REPORTS_WITH_PREPARED_REPORT_DISABLED


def disable_prepared_reports():
	"""Reset managed reports after ERPNext's report JSON files are synced."""
	frappe.db.set_value(
		"Report",
		{"name": ("in", REPORTS_WITH_PREPARED_REPORT_DISABLED)},
		"prepared_report",
		0,
		update_modified=False,
	)


@frappe.whitelist()
def disable_prepared_report(report_name: str):
	"""Allow a report reader to turn off Prepared Report for a managed report."""
	if not is_prepared_report_disabled(report_name):
		frappe.throw(
			_("Prepared Report is not managed for report {0}.").format(frappe.bold(report_name)),
			frappe.ValidationError,
		)

	report = frappe.get_doc("Report", report_name)
	report.check_permission("read")

	frappe.db.set_value(
		"Report",
		report_name,
		"prepared_report",
		0,
		update_modified=False,
	)

	return {"report_name": report_name, "prepared_report": 0}
