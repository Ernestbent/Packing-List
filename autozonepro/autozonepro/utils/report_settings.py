import frappe


@frappe.whitelist()
def disable_prepared_report(report_name: str):
	"""Allow a report reader to turn off Prepared Report."""
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
