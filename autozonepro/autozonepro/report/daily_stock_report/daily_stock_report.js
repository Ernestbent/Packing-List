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
				return "";
			}
			if (raw === 0) {
				return '<span style="color: #bbb;">0</span>';
			}
			if (raw < 0) {
				return `<span style="color: #e74c3c; font-weight: 600;">${raw}</span>`;
			}
		}
		return value;
	},
};
