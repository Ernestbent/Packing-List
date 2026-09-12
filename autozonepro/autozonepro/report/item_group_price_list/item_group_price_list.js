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
			fieldname: "model",
			label: "Model",
			fieldtype: "MultiSelectList",
			placeholder: __("Model"),
			get_data(txt) {
				return frappe.call({
					method:
						"autozonepro.autozonepro.report.item_group_price_list.item_group_price_list.get_model_options",
					args: { txt },
				}).then((r) => r.message || []);
			},
		},
	],

	formatter(value, row, column, data, default_formatter) {
		const formatted_value = default_formatter(value, row, column, data);

		if (column.fieldname === "brand") {
			return `<div style="width: 100%; text-align: left;">${formatted_value}</div>`;
		}

		if (column.fieldtype === "Currency") {
			const price = data && data[column.fieldname];
			const image = data?.model_images?.[column.fieldname];

			if (price === null || price === undefined || price === "") {
				return "";
			}

			const whole_price = Math.round(Number(price)).toLocaleString("en-US");
			const price_html = `<div style="width:100%; text-align:right; font-weight:600;">${whole_price}</div>`;

			if (!image) {
				return price_html;
			}

			const image_url = frappe.utils.escape_html(image);
			return `
				<div style="display:flex; align-items:center; justify-content:flex-end; gap:8px; width:100%;">
					<a href="${image_url}" target="_blank" rel="noopener noreferrer">
						<img src="${image_url}"
							style="width:44px; height:36px; object-fit:contain; border:1px solid #d1d8dd; border-radius:4px; background:#fff;"
							onerror="this.closest('a').style.display='none'">
					</a>
					${price_html}
				</div>`;
		}

		return formatted_value;
	},
};
