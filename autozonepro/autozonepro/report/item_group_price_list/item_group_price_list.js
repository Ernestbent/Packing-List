// Filters for Item Group Price List report
frappe.query_reports["Item Group Price List"] = {
	filters: [
		{
			fieldname: "item_group",
			label: "Item Group",
			fieldtype: "Link",
			options: "Item Group",
		},
		{
			fieldname: "brand",
			label: "Brand",
			fieldtype: "Link",
			options: "Brand",
		},
	],

	formatter(value, row, column, data, default_formatter) {
		const formatted_value = default_formatter(value, row, column, data);

		if (column.fieldname === "brand") {
			return `<div style="width: 100%; text-align: left;">${formatted_value}</div>`;
		}

		if (column.fieldtype === "Currency") {
			const price = data && data[column.fieldname];

			if (price === null || price === undefined || price === "") {
				return "";
			}

			const whole_price = Math.round(Number(price)).toLocaleString("en-US");
			return `<div style="width: 100%; text-align: right;">${whole_price}</div>`;
		}

		return formatted_value;
	},
};
