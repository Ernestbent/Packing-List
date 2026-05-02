// Copyright (c) 2026, Ernest Benedict and contributors
// For license information, please see license.txt

frappe.ui.form.on("Return Stock", {
    setup(frm) {
        frm.set_query("customer", "table_mwme", () => {
            if (!frm.doc.sales_person) {
                return {
                    filters: { name: ["=", ""] },
                };
            }

            return {
                query: "autozonepro.autozonepro.doctype.return_stock.return_stock.get_sales_person_customers",
                filters: {
                    sales_person: frm.doc.sales_person,
                },
            };
        });
    },

    sales_person(frm) {
        // Clear existing rows when salesperson changes to avoid mismatched assignments.
        (frm.doc.table_mwme || []).forEach((row) => {
            row.customer = "";
        });
        frm.refresh_field("table_mwme");
        calculate_totals(frm);
    },
});

frappe.ui.form.on("Return Customer", {
    boxes(frm) {
        calculate_totals(frm);
    },
    amount(frm) {
        calculate_totals(frm);
    },
    table_mwme_remove(frm) {
        calculate_totals(frm);
    },
});

function calculate_totals(frm) {
    let total_boxes = 0;
    let total_amount = 0;

    (frm.doc.table_mwme || []).forEach((row) => {
        total_boxes += Number(row.boxes) || 0;
        total_amount += Number(row.amount) || 0;
    });

    frm.set_value("total_boxes", total_boxes);
    frm.set_value("total_amount", total_amount);
}
