// Copyright (c) 2024, Your Company and contributors
// For license information, please see license.txt

frappe.query_reports["Complete Price List Report"] = {
    "filters": [
        {
            "fieldname": "company",
            "label": __("Company"),
            "fieldtype": "Link",
            "options": "Company",
            "default": frappe.defaults.get_user_default("Company"),
            "reqd": 1
        },
        {
            "fieldname": "item_code",
            "label": __("Item Code"),
            "fieldtype": "Link",
            "options": "Item",
            "get_query": function() {
                return {
                    filters: {
                        "disabled": 0
                    }
                };
            }
        },
        {
            "fieldname": "brand",
            "label": __("Brand"),
            "fieldtype": "Link",
            "options": "Brand"
        },
        {
            "fieldname": "show_only_with_prices",
            "label": __("Show Only Items With Prices"),
            "fieldtype": "Check",
            "default": 0
        }
    ],

    "formatter": function(value, row, column, data, default_formatter) {
        value = default_formatter(value, row, column, data);

        // Highlight missing prices with orange dash
        if (!value || value === "Not Set" || value === "N/A" || value === 0) {
            value = `<span style="color: #FF9800;">-</span>`;
        }

        // Highlight calculated stockist price in blue
        if (column.fieldname === "stockist_selling" && data && data.calculated_stockist) {
            value = `<span style="color: #2196F3; font-weight: bold;">${value}*</span>`;
        }

        // Highlight calculated distributor price in blue
        if (column.fieldname === "distributor_price" && data && data.calculated_distributor) {
            value = `<span style="color: #2196F3; font-weight: bold;">${value}*</span>`;
        }

        // Highlight calculated retailer price in blue
        if (column.fieldname === "retailer_price" && data && data.calculated_retailer) {
            value = `<span style="color: #2196F3; font-weight: bold;">${value}*</span>`;
        }

        // Highlight Grand Total column in green
        if (column.fieldname === "grand_total" && value && value !== "-") {
            value = `<span style="font-weight: bold; color: #4CAF50;">${value}</span>`;
        }

        return value;
    },

    "onload": function(report) {
        // Add export to Excel button
        report.page.add_inner_button(__("Export to Excel"), function() {
            export_report_to_excel(report);
        });

        // Add refresh button
        report.page.add_inner_button(__("Refresh"), function() {
            report.refresh();
        });
    }
};

// Export report data to CSV file
function export_report_to_excel(report) {
    let data = report.data;
    if (!data || data.length === 0) {
        frappe.msgprint(__("No data to export"));
        return;
    }

    let csv_content = [];

    // Define report headers
    let headers = [
        "Item Code",
        "Item Description",
        "Brand",
        "Standard Buying",
        "Standard Selling",
        "Stockist Selling",
        "Distributor Price",
        "Retailer Price",
        "Verma Price List",
        "Grand Total"
    ];

    // Add headers to CSV
    csv_content.push(headers.map(h => `"${h}"`).join(","));

    // Add data rows to CSV
    data.forEach(row => {
        let row_values = [
            row.item_code,
            row.item_description,
            row.brand,
            row.standard_buying,
            row.standard_selling,
            row.stockist_selling,
            row.distributor_price,
            row.retailer_price,
            row.verma_price,
            row.grand_total
        ];

        // Clean values for proper CSV format
        row_values = row_values.map(v => {
            if (v === undefined || v === null) return "";
            if (typeof v === "string" && (v.includes(",") || v.includes('"'))) {
                v = `"${v.replace(/"/g, '""')}"`;
            }
            return v;
        });

        csv_content.push(row_values.join(","));
    });

    // Create blob and download
    let blob = new Blob(["\uFEFF" + csv_content.join("\n")], { type: "text/csv;charset=utf-8;" });
    let link = document.createElement("a");
    let url = URL.createObjectURL(blob);
    link.href = url;
    link.setAttribute("download", `price_list_report_${frappe.datetime.nowdate()}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
}