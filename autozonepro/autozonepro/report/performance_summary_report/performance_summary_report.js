frappe.query_reports["Performance Summary Report"] = {
    filters: [
        {
            // Month filter — defaults to the current month
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
            // Year filter — defaults to the current year
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

        // Only style rows flagged as summary rows from the Python backend
        if (!data || !data._is_summary) return value;

        // Highlight Total of All column in green
        const isTotal = column.fieldname === "total_all";

        // Highlight Daily Avg column in amber
        const isAvg = column.fieldname === "daily_avg";

        // No. column gets a muted grey so it reads as an index not data
        const isNo = column.fieldname === "no";

        // Pick background based on column type
        const bg = isTotal ? "#d5f5e3"
                 : isAvg   ? "#fef9e7"
                 : isNo    ? "#f0f0f0"
                 :           "#eaf4fb";

        return `<span style="
            display: block;
            background-color: ${bg};
            border-bottom: 1px solid #d5e8f0;
            font-size: 12px;
            font-weight: ${isTotal || isAvg ? "700" : "500"};
            padding: 4px 6px;
            color: #1a252f;
        ">${value !== null && value !== undefined ? value : ""}</span>`;
    }
};