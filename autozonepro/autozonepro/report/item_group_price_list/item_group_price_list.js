// Filters for Item Group Price List report
frappe.query_reports["Item Group Price List"] = {
	onload(report) {
		report.page.add_inner_button(__("Download With Images"), () => {
			open_url_post(frappe.request.url, {
				cmd:
					"autozonepro.autozonepro.report.item_group_price_list.item_group_price_list.download_xlsx_with_images",
				filters: frappe.query_report.get_filter_values(),
			});
		});
	},

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
		if (column.fieldname === "picture") {
			if (!value) {
				return "";
			}

			const image_url = frappe.utils.escape_html(value);
			return `
				<div style="display:flex; align-items:center; justify-content:center; width:100%; height:64px;">
					<a href="${image_url}" target="_blank" rel="noopener noreferrer">
						<img src="${image_url}"
							style="display:block; max-width:80px; max-height:60px; width:auto; height:auto; object-fit:contain; border:0; border-radius:0; background:transparent;"
							onerror="this.closest('a').style.display='none'">
					</a>
				</div>`;
		}

		const formatted_value = default_formatter(value, row, column, data);

		if (column.fieldname === "brand") {
			return `<div style="width:100%; text-align:left;">${formatted_value}</div>`;
		}

		if (column.fieldtype === "Currency") {
			const price = data && data[column.fieldname];
			if (price === null || price === undefined || price === "") {
				return "";
			}
			const whole_price = Math.round(Number(price)).toLocaleString("en-US");
			const item_code = data && data._item_codes && data._item_codes[column.fieldname];
			if (!item_code) {
				return `<div style="width:100%; text-align:right; font-weight:600;">${whole_price}</div>`;
			}

			const item_url = frappe.utils.escape_html(
				frappe.utils.get_form_link("Item", item_code)
			);
			return `<div style="width:100%; text-align:right; font-weight:600;"><a href="${item_url}">${whole_price}</a></div>`;
		}

		return formatted_value;
	},

	after_datatable_render() {
		const wrapper = frappe.query_report.$report_wrapper;

		$(wrapper).addClass("item-group-price-list-report");

		if (!document.getElementById("item-group-price-list-style")) {
			const style = document.createElement("style");
			style.id = "item-group-price-list-style";
			style.innerHTML = `
				.item-group-price-list-report .datatable .dt-scrollable .dt-row {
					height: 80px !important;
				}
				.item-group-price-list-report .datatable .dt-scrollable .dt-cell {
					height: 80px !important;
				}
				.item-group-price-list-report .datatable .dt-scrollable .dt-cell__content {
					min-height: 78px;
					padding-top: 6px;
					padding-bottom: 6px;
					line-height: 1.35;
					display: flex;
					align-items: center;
				}
			`;
			document.head.appendChild(style);
		}

	},

	get_datatable_options(options) {
		return Object.assign(options, {
			cellHeight: 80,
			inlineFilters: false,
		});
	},
};
