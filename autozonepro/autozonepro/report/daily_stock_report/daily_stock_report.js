frappe.query_reports["Daily Stock Report"] = {
    "filters": [
        {
            "fieldname": "year",
            "label": __("Year"),
            "fieldtype": "Select",
            "options": get_year_options(),
            "default": frappe.datetime.get_today().split("-")[0],
            "reqd": 1
        },
        {
            "fieldname": "month",
            "label": __("Month"),
            "fieldtype": "Select",
            "options": [
                { "value": "1",  "label": __("January")   },
                { "value": "2",  "label": __("February")  },
                { "value": "3",  "label": __("March")     },
                { "value": "4",  "label": __("April")     },
                { "value": "5",  "label": __("May")       },
                { "value": "6",  "label": __("June")      },
                { "value": "7",  "label": __("July")      },
                { "value": "8",  "label": __("August")    },
                { "value": "9",  "label": __("September") },
                { "value": "10", "label": __("October")   },
                { "value": "11", "label": __("November")  },
                { "value": "12", "label": __("December")  }
            ],
            "default": String(frappe.datetime.get_today().split("-")[1].replace(/^0/, "")),
            "reqd": 1
        },
        {
            "fieldname": "warehouse",
            "label": __("Warehouse"),
            "fieldtype": "Link",
            "options": "Warehouse"
        },
        {
            "fieldname": "item_code",
            "label": __("Item"),
            "fieldtype": "Link",
            "options": "Item"
        },
        {
            "fieldname": "item_group",
            "label": __("Item Group"),
            "fieldtype": "Link",
            "options": "Item Group"
        }
    ],

    "formatter": function(value, row, column, data, default_formatter) {
        value = default_formatter(value, row, column, data);

        if (column.fieldname && column.fieldname.startsWith("day_")) {
            let raw = data[column.fieldname];
            if (raw === null || raw === undefined || raw === 0) {
                value = '<span style="color: #bbb;">0</span>';
            } else if (raw < 0) {
                value = '<span style="color: #e74c3c; font-weight: 600;">' + raw + '</span>';
            }
        }

        return value;
    },

    "onload": function(report) {
        report.page.add_inner_button(__("Export to Excel"), function() {
            report.export_report("Excel");
        });
    }
};

function get_year_options() {
    let current_year = frappe.datetime.get_today().split("-")[0];
    let years = [];
    for (let y = parseInt(current_year) + 1; y >= parseInt(current_year) - 5; y--) {
        years.push(String(y));
    }
    return years.join("\n");
}