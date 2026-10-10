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


def disable_all_prepared_reports():
	"""Reset reports previously auto-promoted to Prepared Report mode."""
	report_names = frappe.get_all(
		"Report",
		filters={"prepared_report": 1},
		pluck="name",
	)
	if report_names:
		frappe.db.set_value(
			"Report",
			{"name": ("in", report_names)},
			"prepared_report",
			0,
			update_modified=False,
		)
		frappe.clear_cache(doctype="Report")

	return report_names
