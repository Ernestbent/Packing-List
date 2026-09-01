frappe.query_reports["Daily Stock Report"] = {
	filters: [
		{
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date",
			default: frappe.datetime.month_start(),
			reqd: 1,
		},
		{
			fieldname: "to_date",
			label: __("To Date"),
			fieldtype: "Date",
			default: frappe.datetime.get_today(),
			reqd: 1,
		},
		{
			fieldname: "warehouse",
			label: __("Warehouse"),
			fieldtype: "Link",
			options: "Warehouse",
		},
		{
			fieldname: "item_code",
			label: __("Item"),
			fieldtype: "Link",
			options: "Item",
		},
		{
			fieldname: "item_group",
			label: __("Item Group"),
			fieldtype: "Link",
			options: "Item Group",
		},
	],

	formatter(value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);
		if (column.fieldname && column.fieldname.startsWith("date_")) {
			const raw = data[column.fieldname];
			if (raw === null || raw === undefined) {
				value = "";
			} else if (raw === 0) {
				value = '<span style="color: #bbb;">0</span>';
			} else if (raw < 0) {
				value = `<span style="color: #e74c3c; font-weight: 600;">${raw}</span>`;
			}
		}
		return value;
	},

	onload(report) {
		report.page.add_inner_button(__("Export to Excel"), () => {
			open_export_dialog(report, "Excel");
		});
		report.page.add_inner_button(__("Export to CSV"), () => {
			open_export_dialog(report, "CSV");
		});
	},
};

function open_export_dialog(report, file_format) {
	report.export_report();
	if (report.export_dialog) {
		report.export_dialog.set_value("file_format", file_format);
	}
}
