// Copyright (c) 2016, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

const unique_item_tree_types = ["Customer", "Region", "District", "Sales Person", "Route", "Item"];
const secondary_filter_options = [
	"",
	"Customer Group",
	"Customer",
	"Region",
	"District",
	"Sales Person",
	"Item Group",
	"Item",
	"Route",
	"Order Type",
	"Project",
];

const get_secondary_filter_fields = () =>
	[1, 2, 3, 4, 5].flatMap((index) => {
		const suffix = index === 1 ? "" : `_${index}`;
		const previous_suffix = index === 2 ? "" : `_${index - 1}`;
		const depends_on =
			index === 1
				? undefined
				: `eval: doc.secondary_filter_by${previous_suffix} && doc.secondary_filter_value${previous_suffix}`;

		return [
			{
				fieldname: `secondary_filter_by${suffix}`,
				label: __(`Filter ${index} By`),
				fieldtype: "Select",
				options: secondary_filter_options,
				depends_on,
				on_change(report) {
					report.set_filter_value(`secondary_filter_value${suffix}`, "");
					for (let next = index + 1; next <= 5; next++) {
						report.set_filter_value(`secondary_filter_by_${next}`, "");
						report.set_filter_value(`secondary_filter_value_${next}`, "");
					}
				},
			},
			{
				fieldname: `secondary_filter_value${suffix}`,
				label: __(`Filter ${index} Value`),
				fieldtype: "Autocomplete",
				placeholder: __("Select Value"),
				depends_on: `eval: doc.secondary_filter_by${suffix}`,
				get_query() {
					return {
						query:
							"autozonepro.autozonepro.report.sales_analytics_apl.sales_analytics_apl.get_secondary_filter_options",
						params: {
							filter_by: frappe.query_report.get_filter_value(
								`secondary_filter_by${suffix}`
							),
						},
					};
				},
			},
		];
	});

const get_value_quantity_options = (tree_type) => {
	const options = [
		{ value: "Value", label: __("Value") },
		{ value: "Quantity", label: __("Quantity") },
	];
	if (unique_item_tree_types.includes(tree_type)) {
		options.push({ value: "Unique Items", label: __("Unique Items") });
	}
	if (tree_type === "Item") {
		options.push({ value: "Customer Count", label: __("Customer Count") });
	}
	return options;
};

const update_value_quantity_options = (report, refresh_report = false) => {
	const tree_type = report.get_filter_value("tree_type");
	const value_filter = report.get_filter("value_quantity");
	if (!value_filter) return;

	const options = get_value_quantity_options(tree_type);
	const current_value = value_filter.get_value();
	value_filter.df.options = options;
	value_filter.set_options(current_value);

	if (!options.some((option) => option.value === current_value)) {
		report.set_filter_value("value_quantity", "Value");
	} else if (refresh_report) {
		report.refresh(true);
	}
};

frappe.query_reports["Sales Analytics APL"] = {
	onload(report) {
		update_value_quantity_options(report);
	},
	filters: [
		{
			fieldname: "tree_type",
			label: __("Tree Type"),
			fieldtype: "Select",
			options: [
				"Customer Group",
				"Customer",
				"Region",
				"District",
				"Sales Person",
				"Item Group",
				"Item",
				"Route",
				"Order Type",
				"Project",
			],
			default: "Customer",
			reqd: 1,
			on_change(report) {
				update_value_quantity_options(report, true);
			},
		},
		{
			fieldname: "doc_type",
			label: __("based_on"),
			fieldtype: "Select",
			options: ["Sales Order", "Delivery Note", "Sales Invoice", "Sales Loss"],
			default: "Sales Invoice",
			reqd: 1,
		},
		{
			fieldname: "value_quantity",
			label: __("Value Or Qty"),
			fieldtype: "Select",
			options: get_value_quantity_options("Customer"),
			default: "Value",
			reqd: 1,
		},
		{
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date",
			default: erpnext.utils.get_fiscal_year(frappe.datetime.get_today(), true)[1],
			reqd: 1,
		},
		{
			fieldname: "to_date",
			label: __("To Date"),
			fieldtype: "Date",
			default: erpnext.utils.get_fiscal_year(frappe.datetime.get_today(), true)[2],
			reqd: 1,
		},
		{
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
			default: frappe.defaults.get_user_default("Company"),
			reqd: 1,
		},
		{
			fieldname: "item_classification",
			label: __("Item Classification"),
			fieldtype: "Select",
			options: [
				{ value: "Focus Items", label: __("Focus Items") },
				{ value: "Slow Moving Items", label: __("Slow Moving Items") },
				{ value: "All", label: __("All") },
			],
			default: "All",
			reqd: 1,
			depends_on: "eval: doc.tree_type == 'Item'",
		},
		{
			fieldname: "item_dimension",
			label: __("Item Analysis By"),
			fieldtype: "Select",
			options: [
				{ value: "Brand", label: __("Brand") },
				{ value: "Model", label: __("Model") },
				{ value: "Description", label: __("Description") },
				{ value: "Group", label: __("Group") },
			],
			default: "Brand",
			reqd: 1,
			depends_on: "eval: doc.tree_type == 'Item'",
		},
		...get_secondary_filter_fields(),
		{
			fieldname: "range",
			label: __("Range"),
			fieldtype: "Select",
			options: [
				{ value: "Daily", label: __("Daily") },
				{ value: "Weekly", label: __("Weekly") },
				{ value: "Monthly", label: __("Monthly") },
				{ value: "Quarterly", label: __("Quarterly") },
				{ value: "Yearly", label: __("Yearly") },
			],
			default: "Monthly",
			reqd: 1,
		},
		{
			fieldname: "curves",
			label: __("Curves"),
			fieldtype: "Select",
			options: [
				{ value: "all", label: __("All") },
				{ value: "non-zeros", label: __("Non-Zeros") },
				{ value: "total", label: __("Total Only") },
			],
			default: "all",
			reqd: 1,
		},
		{
			fieldname: "show_aggregate_value_from_subsidiary_companies",
			label: __("Show Aggregate Value from Subsidiary Companies"),
			fieldtype: "Check",
		},
	],
	get_datatable_options(options) {
		return Object.assign(options, {
			checkboxColumn: true,
			events: {
				onCheckRow: function (data) {
					if (!data) return;
					const data_doctype = data[2].html
						? $(data[2].html).attr("data-doctype")
						: null;
					const selected_tree_type = frappe.query_report.filters[0].value;
					const item_dimension = frappe.query_report.get_filter_value("item_dimension");
					const tree_type = selected_tree_type === "Route" ? "Territory" : selected_tree_type;
					if (data_doctype && data_doctype != tree_type) return;

					const row_name = data[2].content;
					const raw_data = frappe.query_report.chart.data;
					const new_datasets = raw_data.datasets;
					const element_found = new_datasets.some((element, index, array) => {
						if (element.name == row_name) {
							array.splice(index, 1);
							return true;
						}
						return false;
					});
					const slice_at =
						{ Customer: 4, Item: item_dimension ? 7 : 6 }[selected_tree_type] || 3;

					if (!element_found) {
						new_datasets.push({
							name: row_name,
							values: data.slice(slice_at, data.length - 1).map((column) => column.content),
						});
					}

					const new_data = {
						labels: raw_data.labels,
						datasets: new_datasets,
					};
					const new_options = Object.assign({}, frappe.query_report.chart_options, {
						data: new_data,
					});
					frappe.query_report.render_chart(new_options);

					frappe.query_report.raw_chart_data = new_data;
				},
			},
		});
	},
};
