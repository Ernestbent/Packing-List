frappe.query_reports["Performance Sheet"] = {
    filters: [
        {
            // Month filter — defaults to current month
            fieldname: "month",
            label: __("Month"),
            fieldtype: "Select",
            options: [
                { value: 1,  label: __("January") },
                { value: 2,  label: __("February") },
                { value: 3,  label: __("March") },
                { value: 4,  label: __("April") },
                { value: 5,  label: __("May") },
                { value: 6,  label: __("June") },
                { value: 7,  label: __("July") },
                { value: 8,  label: __("August") },
                { value: 9,  label: __("September") },
                { value: 10, label: __("October") },
                { value: 11, label: __("November") },
                { value: 12, label: __("December") }
            ],
            default: new Date().getMonth() + 1,
            reqd: 1
        },
        {
            // Year filter — defaults to current year
            fieldname: "year",
            label: __("Year"),
            fieldtype: "Select",
            options: [2024, 2025, 2026, 2027],
            default: new Date().getFullYear(),
            reqd: 1
        }
    ],

    formatter: function(value, row, column, data, default_formatter) {
        value = default_formatter(value, row, column, data);
        if (!data) return value;

        const val = value !== null && value !== undefined ? value : "";

        const summaryFields = [
            "total", "daily_avg", "total_all_4", "overall_daily_avg",
            "total_packing", "total_picking", "total_verified",
            "total_billing", "total_dispatched"
        ];
        const isSummaryCol = summaryFields.includes(column.fieldname);
        const isCombined   = ["total_all_4", "overall_daily_avg"].includes(column.fieldname);

        // First row of each person group — red top border to visually separate people
        if (data._is_first_row) {
            return `<span style="
                display: block;
                background-color: #fff0f0;
                border-top: 2px solid #e74c3c;
                padding: 2px 4px;
                font-weight: 600;
            ">${val}</span>`;
        }

        // Last row of each person group — green tint, bold on combined totals only
        if (data._is_last_row) {
            return `<span style="
                display: block;
                background-color: #eafaf1;
                padding: 2px 4px;
                font-weight: ${isCombined ? "700" : "500"};
                color: ${isCombined ? "#1a5e36" : "#1a252f"};
            ">${val}</span>`;
        }

        // Summary columns on middle rows — subtle blue tint
        if (isSummaryCol) {
            return `<span style="
                display: block;
                background-color: #eaf4fb;
                padding: 2px 4px;
                font-weight: 600;
            ">${val}</span>`;
        }

        return value;
    }
};