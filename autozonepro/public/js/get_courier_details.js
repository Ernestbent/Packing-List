frappe.ui.form.on("Sales Order", {
    before_workflow_action: function (frm) {
        console.log("Workflow action triggered:", frm.selected_workflow_action);

        if (frm.selected_workflow_action === "Enter Courier Details") {
            return new Promise((resolve, reject) => {
                frappe.dom.unfreeze();

                // Find Packing List directly via custom_sales_order
                frappe.call({
                    method: "frappe.client.get_list",
                    args: {
                        doctype: "Packing List",
                        filters: { custom_sales_order: frm.doc.name },
                        fields: ["name"],
                        order_by: "`tabPacking List`.creation desc",
                        limit_page_length: 1
                    },
                    callback: function(pl_res) {
                        if (pl_res.message && pl_res.message.length > 0) {
                            let pl_name = pl_res.message[0].name;
                            console.log("Found Packing List:", pl_name);

                            frappe.call({
                                method: "frappe.client.get",
                                args: { doctype: "Packing List", name: pl_name },
                                callback: function(pl_doc_res) {
                                    let rows = pl_doc_res.message.custom_box_summary || [];
                                    show_courier_dialog(frm, resolve, reject, pl_name, rows);
                                }
                            });
                        } else {
                            console.log("No Packing List found for Sales Order:", frm.doc.name);
                            show_courier_dialog(frm, resolve, reject, null, []);
                        }
                    }
                });
            });
        }

        // ─────────────────────────────────────────────
        // ACTION: Mark As Delivered
        // ─────────────────────────────────────────────
        if (frm.selected_workflow_action === "Mark As Delivered") {
            return new Promise((resolve, reject) => {
                frappe.dom.unfreeze();

                let d = new frappe.ui.Dialog({
                    title: "Update Delivery Note Received Date",
                    fields: [
                        {
                            label: "Received Date",
                            fieldname: "delivery_date",
                            fieldtype: "Date",
                            reqd: 1,
                            default: frappe.datetime.get_today()
                        },
                        {
                            label: "Customer Remarks",
                            fieldname: "custom_remarks_customer",
                            fieldtype: "Small Text",
                            default: frm.doc.custom_remarks_customer || ""
                        }
                    ],
                    primary_action_label: "Update & Continue",
                    primary_action(values) {
                        if (!values.delivery_date) {
                            frappe.msgprint({
                                title: __("Required"),
                                indicator: "red",
                                message: __("Please select a delivery date before continuing.")
                            });
                            return;
                        }

                        d.get_primary_btn().attr("disabled", true);

                        frappe.call({
                            method: "autozonepro.autozonepro.custom_scripts.update_dn_date.update_delivery_date",
                            args: {
                                sales_order: frm.doc.name,
                                delivery_date: values.delivery_date,
                                custom_remarks_customer: values.custom_remarks_customer
                            },
                            freeze: true,
                            freeze_message: __("Updating Delivery Date..."),
                            callback: function(r) {
                                frappe.dom.unfreeze();
                                d.get_primary_btn().attr("disabled", false);
                                if (!r.exc) {
                                    frappe.msgprint({
                                        title: "Success",
                                        indicator: "green",
                                        message: `Updated: ${r.message.join(", ") || "None"}`
                                    });
                                    d.hide();
                                    resolve();
                                } else {
                                    frappe.msgprint({
                                        title: "Error",
                                        indicator: "red",
                                        message: `Failed: ${r.exc || "Unknown error"}`
                                    });
                                    reject();
                                }
                            },
                            error: function(err) {
                                frappe.dom.unfreeze();
                                d.get_primary_btn().attr("disabled", false);
                                frappe.msgprint({
                                    title: "Error",
                                    indicator: "red",
                                    message: `Error: ${err.message || "Unknown"}`
                                });
                                reject();
                            }
                        });
                    },
                    secondary_action_label: "Cancel",
                    secondary_action() {
                        d.hide();
                        frappe.msgprint({
                            title: __("Cancelled"),
                            indicator: "orange",
                            message: __("Workflow transition cancelled.")
                        });
                        reject();
                    }
                });

                d.show();
            });
        }
    }
});


function show_courier_dialog(frm, resolve, reject, pl_name, box_rows) {

    const STORAGE_KEY = `courier_draft_${frm.doc.name}`;

    let saved_draft = {};
    try {
        let raw = localStorage.getItem(STORAGE_KEY);
        if (raw) saved_draft = JSON.parse(raw);
    } catch(e) {}

    function save_draft(d, expense_overrides) {
        try {
            let draft = {
                first_name: d.get_value("first_name") || "",
                surname: d.get_value("surname") || "",
                tel_no: d.get_value("tel_no") || "",
                vehicle_no: d.get_value("vehicle_no") || "",
                expenses: expense_overrides || {}
            };
            localStorage.setItem(STORAGE_KEY, JSON.stringify(draft));
        } catch(e) {}
    }

    function clear_draft() {
        try { localStorage.removeItem(STORAGE_KEY); } catch(e) {}
    }

    function build_box_table(rows) {
        if (!rows || rows.length === 0) {
            return `<p style="color:orange;margin:8px 0;">
                        ${pl_name
                            ? `Packing List <b>${pl_name}</b> found but Box Summary is empty.`
                            : "No Packing List found linked to this Sales Order."
                        }
                    </p>`;
        }

        let body = rows.map((row, idx) => {
            let saved_expense = (saved_draft.expenses && saved_draft.expenses[idx] !== undefined)
                ? saved_draft.expenses[idx]
                : (row.expense || "");

            return `
                <tr>
                    <td style="padding:6px 10px;border:1px solid #d1d8dd;">${row.box_number || ""}</td>
                    <td style="padding:6px 10px;border:1px solid #d1d8dd;">${row.weight_kg || ""}</td>
                    <td style="padding:4px 8px;border:1px solid #d1d8dd;">
                        <input
                            type="number"
                            class="expense-input form-control"
                            data-idx="${idx}"
                            value="${saved_expense}"
                            placeholder="0.00"
                            step="0.01"
                            style="width:100%;font-size:13px;"
                        />
                    </td>
                </tr>`;
        }).join("");

        return `
            <table style="width:100%;border-collapse:collapse;font-size:13px;margin-top:8px;">
                <thead>
                    <tr style="background:#f4f5f6;">
                        <th style="padding:8px 10px;border:1px solid #d1d8dd;text-align:left;font-weight:600;">Box Number</th>
                        <th style="padding:8px 10px;border:1px solid #d1d8dd;text-align:left;font-weight:600;">Weight (Kg)</th>
                        <th style="padding:8px 10px;border:1px solid #d1d8dd;text-align:left;font-weight:600;">Expense</th>
                    </tr>
                </thead>
                <tbody>${body}</tbody>
            </table>`;
    }

    let pl_label = pl_name
        ? `<p style="font-weight:600;margin-bottom:6px;font-size:13px;">
               📦 Box Summary from:
               <a href="/app/packing-list/${pl_name}" target="_blank">${pl_name}</a>
           </p>`
        : `<p style="color:orange;margin-bottom:6px;">⚠️ No Packing List found for this Sales Order.</p>`;

    let draft_banner = Object.keys(saved_draft).length > 0
        ? `<div style="background:#fff9e6;border:1px solid #f5c518;border-radius:4px;padding:8px 12px;margin-bottom:12px;font-size:12px;">
               ⚡ <b>Draft restored</b> — your previous entries have been reloaded.
           </div>`
        : "";

    let d = new frappe.ui.Dialog({
        title: "Enter Courier Details",
        fields: [
            { fieldname: "draft_notice", fieldtype: "HTML", options: draft_banner },
            { fieldtype: "Section Break", label: "Driver Details" },
            {
                label: "First Name", fieldname: "first_name", fieldtype: "Data",
                reqd: 1, default: saved_draft.first_name || ""
            },
            {
                label: "Surname", fieldname: "surname", fieldtype: "Data",
                reqd: 1, default: saved_draft.surname || ""
            },
            {
                label: "Full Name", fieldname: "full_name", fieldtype: "Data",
                read_only: 1,
                default: (saved_draft.first_name && saved_draft.surname)
                    ? `${saved_draft.first_name} ${saved_draft.surname}`.trim() : ""
            },
            { fieldtype: "Column Break" },
            {
                label: "Tel No", fieldname: "tel_no", fieldtype: "Data",
                reqd: 1, default: saved_draft.tel_no || ""
            },
            {
                label: "Vehicle No", fieldname: "vehicle_no", fieldtype: "Data",
                reqd: 1, default: saved_draft.vehicle_no || ""
            },
            { fieldtype: "Section Break", label: "Shipping Costs" },
            {
                fieldname: "box_summary_html", fieldtype: "HTML",
                options: pl_label + build_box_table(box_rows)
            }
        ],
        primary_action_label: "Create & Proceed",
        primary_action(values) {
            if (!values.first_name || !values.surname || !values.tel_no || !values.vehicle_no) {
                frappe.msgprint({ title: __("Required"), indicator: "red", message: __("Please fill all required fields.") });
                return;
            }

            let expense_overrides = {};
            let updated_rows = box_rows.map((row, idx) => {
                let input = d.$wrapper.find(`.expense-input[data-idx="${idx}"]`);
                let expense_val = input.length ? parseFloat(input.val()) || 0 : (row.expense || 0);
                expense_overrides[idx] = expense_val;
                return { box_number: row.box_number || 0, weight_kg: row.weight_kg || 0, expense: expense_val };
            });

            d.get_primary_btn().attr("disabled", true);

            frappe.call({
                method: "autozonepro.autozonepro.custom_scripts.get_courier_details.create_courier_details",
                args: {
                    sales_order: frm.doc.name,
                    first_name: values.first_name,
                    surname: values.surname,
                    tel_no: values.tel_no,
                    vehicle_no: values.vehicle_no,
                    packing_list: pl_name || "",
                    box_rows: JSON.stringify(updated_rows)
                },
                freeze: true,
                freeze_message: __("Saving Courier Details..."),
                callback: function(r) {
                    frappe.dom.unfreeze();
                    d.get_primary_btn().attr("disabled", false);
                    if (!r.exc) {
                        clear_draft();
                        frappe.msgprint({ title: "Success", indicator: "green", message: `Courier Details saved: ${r.message.name}` });
                        d.hide();
                        resolve();
                    } else {
                        frappe.msgprint({ title: "Error", indicator: "red", message: `Failed: ${r.exc || "Unknown error"}` });
                        reject();
                    }
                },
                error: function(err) {
                    frappe.dom.unfreeze();
                    d.get_primary_btn().attr("disabled", false);
                    frappe.msgprint({ title: "Error", indicator: "red", message: `Error: ${err.message || "Unknown"}` });
                    reject();
                }
            });
        },
        secondary_action_label: "Cancel",
        secondary_action() {
            let expense_overrides = {};
            box_rows.forEach((row, idx) => {
                let input = d.$wrapper.find(`.expense-input[data-idx="${idx}"]`);
                if (input.length) expense_overrides[idx] = parseFloat(input.val()) || 0;
            });
            save_draft(d, expense_overrides);
            d.hide();
            frappe.show_alert({ message: __("Draft saved. Your entries will be restored next time."), indicator: "blue" });
            reject();
        }
    });

    d.$wrapper.find(".modal-dialog").css({ "max-width": "800px", "width": "90%" });

    d.fields_dict.first_name.$input.on("input", function() {
        d.set_value("full_name", `${d.get_value("first_name") || ""} ${d.get_value("surname") || ""}`.trim());
        save_draft(d, get_current_expenses(d, box_rows));
    });
    d.fields_dict.surname.$input.on("input", function() {
        d.set_value("full_name", `${d.get_value("first_name") || ""} ${d.get_value("surname") || ""}`.trim());
        save_draft(d, get_current_expenses(d, box_rows));
    });
    d.fields_dict.tel_no.$input.on("input", function() { save_draft(d, get_current_expenses(d, box_rows)); });
    d.fields_dict.vehicle_no.$input.on("input", function() { save_draft(d, get_current_expenses(d, box_rows)); });

    d.show();

    d.$wrapper.on("input", ".expense-input", function() { save_draft(d, get_current_expenses(d, box_rows)); });
}

function get_current_expenses(d, box_rows) {
    let expenses = {};
    box_rows.forEach((row, idx) => {
        let input = d.$wrapper.find(`.expense-input[data-idx="${idx}"]`);
        if (input.length) expenses[idx] = parseFloat(input.val()) || 0;
    });
    return expenses;
}