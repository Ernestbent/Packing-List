frappe.query_reports["Performance Sheet"] = {   // ← Change to match your new Report Name
    filters: [
        {
            fieldname: "month",
            label: __("Month"),
            fieldtype: "Select",
            options: [
                { value: 1, label: __("January") },
                { value: 2, label: __("February") },
                { value: 3, label: __("March") },
                { value: 4, label: __("April") },
                { value: 5, label: __("May") },
                { value: 6, label: __("June") },
                { value: 7, label: __("July") },
                { value: 8, label: __("August") },
                { value: 9, label: __("September") },
                { value: 10, label: __("October") },
                { value: 11, label: __("November") },
                { value: 12, label: __("December") }
            ],
            default: new Date().getMonth() + 1,
            reqd: 1
        },
        {
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

        if (data && data._is_first_row) {
            value = `<span style="
                display: block;
                background-color: #fff0f0;
                border-top: 2px solid #e74c3c;
                padding: 2px 4px;
                font-weight: 600;
            ">${value !== null && value !== undefined ? value : ""}</span>`;
        }

        return value;
    }
};