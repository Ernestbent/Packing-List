// Sales Order - Gate Pass generation and workflow validation
// Autozonepro custom app

frappe.after_ajax(() => {
    const _existing = frappe.listview_settings["Sales Order"] || {};
    const _existing_onload = _existing.onload;

    frappe.listview_settings["Sales Order"] = Object.assign(_existing, {
        onload(listview) {
            if (_existing_onload) {
                _existing_onload.call(this, listview);
            }
            // Add Generate Gate Pass button to list view toolbar
            listview.page.add_inner_button(
                "Generate Gate Pass",
                () => show_gate_pass_dialog()
            );
        }
    });
});

// Form level events
frappe.ui.form.on("Sales Order", {

    // Block workflow transition from Billed to In Transit if no gate pass
    before_workflow_action: function(frm) {

        // Only intercept Start Transit action from Billed state
        if (frm.doc.workflow_state !== "Billed") return;

        return new Promise((resolve, reject) => {

            // Check gate pass field is filled
            if (!frm.doc.gate_pass) {
                frappe.msgprint({
                    title: __("Gate Pass Required"),
                    message: __("Sales Order {0} has no linked Gate Pass. Cannot move to 'In Transit'.", [frm.doc.name]),
                    indicator: "red"
                });
                return reject();
            }

            // Fetch the linked gate pass and validate it
            frappe.call({
                method: "frappe.client.get",
                args: {
                    doctype: "Gate Pass",
                    name: frm.doc.gate_pass
                },
                callback: function(r) {

                    if (!r.message) {
                        frappe.msgprint({
                            title: __("Gate Pass Not Found"),
                            message: __("Linked Gate Pass {0} could not be found.", [frm.doc.gate_pass]),
                            indicator: "red"
                        });
                        return reject();
                    }

                    let gp = r.message;
                    let today = frappe.datetime.get_today();

                    // Check gate pass is submitted
                    if (gp.docstatus !== 1) {
                        frappe.msgprint({
                            title: __("Gate Pass Not Submitted"),
                            message: __("Gate Pass {0} is not submitted yet.", [frm.doc.gate_pass]),
                            indicator: "red"
                        });
                        return reject();
                    }

                    // Check gate pass date is today
                    if (gp.date !== today) {
                        frappe.msgprint({
                            title: __("Gate Pass Date Mismatch"),
                            message: __("Gate Pass {0} is dated {1}, not today ({2}).", [frm.doc.gate_pass, gp.date, today]),
                            indicator: "red"
                        });
                        return reject();
                    }

                    // All checks passed, allow transition
                    resolve();
                }
            });
        });
    }
});

// Main dialog for creating a gate pass
function show_gate_pass_dialog() {
    let gate_pass_items = [];

    let d = new frappe.ui.Dialog({
        title: "Generate Gate Pass",
        fields: [
            {
                fieldtype: "Link",
                fieldname: "driver_name",
                label: "Driver Name",
                options: "Driver Details"
            },
            {
                fieldtype: "Column Break"
            },
            {
                fieldtype: "Data",
                fieldname: "vehicle_no",
                label: "Vehicle No"
            },
            {
                fieldtype: "Column Break"
            },
            {
                fieldtype: "Data",
                fieldname: "mileage",
                label: "Mileage"
            },
            {
                fieldtype: "Section Break",
                label: "Add Customer"
            },
            {
                fieldtype: "HTML",
                fieldname: "search_html"
            },
            {
                fieldtype: "Section Break",
                label: "Gate Pass Items"
            },
            {
                fieldtype: "HTML",
                fieldname: "items_html"
            }
        ],
        primary_action_label: "Create Gate Pass",
        primary_action() {
            let v = d.get_values();
            create_gate_pass(d, v, gate_pass_items);
        }
    });

    // Widen the dialog
    d.$wrapper.find(".modal-dialog").css({
        "max-width": "800px",
        "width": "90%"
    });

    // Render customer search input and dropdown
    d.fields_dict.search_html.$wrapper.html(`
        <div style="position:relative;margin-top:5px;">
            <input type="text"
                   id="gp-search-input"
                   placeholder="Type customer name..."
                   autocomplete="off"
                   style="width:100%;
                          padding:8px 14px;
                          border:1px solid #d1d8dd;
                          border-radius:4px;
                          font-size:13px;
                          outline:none;">
            <div id="gp-dropdown"
                 style="display:none;
                        position:absolute;
                        z-index:99999;
                        width:100%;
                        background:#fff;
                        border:1px solid #d1d8dd;
                        border-top:none;
                        border-radius:0 0 6px 6px;
                        max-height:220px;
                        overflow-y:auto;
                        box-shadow:0 6px 16px rgba(0,0,0,0.12);">
            </div>
        </div>
    `);

    // Render empty items table initially
    render_items_table(d, gate_pass_items);

    // Debounced search input handler
    let search_timer;
    d.fields_dict.search_html.$wrapper.on("input", "#gp-search-input", function() {
        let q = $(this).val().trim();
        clearTimeout(search_timer);

        let dropdown = d.fields_dict.search_html.$wrapper.find("#gp-dropdown");

        if (q.length < 1) {
            dropdown.hide().html("");
            return;
        }

        dropdown.html(`
            <div style="padding:10px;text-align:center;color:#aaa;font-size:12px;">
                Searching...
            </div>
        `).show();

        search_timer = setTimeout(() => {
            do_search(q, dropdown, d, gate_pass_items);
        }, 250);
    });

    // Hide dropdown when clicking outside
    $(document).on("mousedown.gp", function(e) {
        if (!$(e.target).closest("#gp-search-input, #gp-dropdown").length) {
            d.fields_dict.search_html.$wrapper.find("#gp-dropdown").hide();
        }
    });

    // Cleanup event on dialog close
    d.onhide = function() {
        $(document).off("mousedown.gp");
    };

    d.show();
}

// Search packing list by customer name and populate dropdown
function do_search(query, dropdown, dialog, gate_pass_items) {
    frappe.call({
        method: "frappe.client.get_list",
        args: {
            doctype: "Packing List",
            filters: [
                ["custom_customer", "like", `%${query}%`],
                ["docstatus", "=", 1]
            ],
            fields: [
                "name",
                "custom_sales_order",
                "custom_customer",
                "custom_date",
                "total_boxes",
                "total_qty"
            ],
            order_by: "custom_date desc",
            limit_page_length: 15
        },
        callback: function(r) {
            if (!r.message || r.message.length === 0) {
                dropdown.html(`
                    <div style="padding:12px;text-align:center;color:#aaa;font-size:12px;">
                        No customers found
                    </div>
                `).show();
                return;
            }

            // Filter out already added packing lists
            let added = gate_pass_items.map(i => i.pl_name);
            let results = r.message.filter(pl => !added.includes(pl.name));

            if (results.length === 0) {
                dropdown.html(`
                    <div style="padding:12px;text-align:center;color:#aaa;font-size:12px;">
                        Already added
                    </div>
                `).show();
                return;
            }

            // Build dropdown rows
            let html = results.map(pl => `
                <div class="gp-item"
                     data-pl="${pl.name}"
                     data-so="${pl.custom_sales_order || ''}"
                     data-customer="${pl.custom_customer || ''}"
                     data-date="${pl.custom_date || ''}"
                     data-boxes="${pl.total_boxes || 0}"
                     data-sku="${pl.total_qty || 0}"
                     style="padding:10px 14px;
                            cursor:pointer;
                            border-bottom:1px solid #f5f5f5;
                            font-size:13px;">
                    <b>${pl.custom_customer || '-'}</b>
                </div>
            `).join("");

            dropdown.html(html).show();

            // Hover and click handlers for dropdown items
            dropdown.find(".gp-item")
                .on("mouseenter", function() {
                    $(this).css("background", "#f0f7ff");
                })
                .on("mouseleave", function() {
                    $(this).css("background", "#fff");
                })
                .on("mousedown", function(e) {
                    e.preventDefault();

                    let item = {
                        pl_name:  $(this).data("pl"),
                        so:       $(this).data("so"),
                        customer: $(this).data("customer"),
                        date:     $(this).data("date"),
                        boxes:    $(this).data("boxes"),
                        sku:      $(this).data("sku")
                    };

                    gate_pass_items.push(item);

                    // Clear search and hide dropdown
                    dialog.fields_dict.search_html.$wrapper
                        .find("#gp-search-input").val("");
                    dropdown.hide().html("");

                    render_items_table(dialog, gate_pass_items);

                    frappe.show_alert({
                        message: `Added: ${item.customer}`,
                        indicator: "green"
                    });
                });
        }
    });
}

// Render the items table inside the dialog
function render_items_table(dialog, items) {
    if (items.length === 0) {
        dialog.fields_dict.items_html.$wrapper.html(`
            <div style="text-align:center;
                        padding:20px;
                        color:#aaa;
                        font-size:12px;
                        border:1px dashed #d1d8dd;
                        border-radius:4px;
                        margin-top:5px;">
                Search and add customers above
            </div>
        `);
        return;
    }

    // Build table rows
    let rows = items.map((item, i) => `
        <tr class="gp-row">
            <td style="width:30px;text-align:center;vertical-align:middle;padding:4px 6px;">
                <button class="btn btn-danger btn-xs remove-item"
                        data-idx="${i}"
                        title="Remove row"
                        style="width:20px;height:20px;padding:0;line-height:1;
                               border-radius:50%;font-size:16px;font-weight:300;
                               display:inline-flex;align-items:center;
                               justify-content:center;border:none;cursor:pointer;">
                    -
                </button>
            </td>
            <td style="text-align:center;vertical-align:middle;">${i + 1}</td>
            <td style="vertical-align:middle;">${item.date || '-'}</td>
            <td style="vertical-align:middle;">
                ${item.so
                    ? `<a href="/app/sales-order/${item.so}" target="_blank" style="font-size:11px;">${item.so}</a>`
                    : '-'
                }
            </td>
            <td style="text-align:left;vertical-align:middle;font-weight:bold;">
                ${item.customer || '-'}
            </td>
            <td style="text-align:center;vertical-align:middle;color:green;font-weight:bold;">
                ${item.boxes || 0}
            </td>
            <td style="text-align:center;vertical-align:middle;">
                ${item.sku || 0}
            </td>
        </tr>
    `).join("");

    // Calculate totals
    let total_boxes = items.reduce((s, i) => s + (parseInt(i.boxes) || 0), 0);
    let total_sku   = items.reduce((s, i) => s + (parseInt(i.sku)   || 0), 0);

    dialog.fields_dict.items_html.$wrapper.html(`
        <div style="max-height:280px;overflow-y:auto;margin-top:5px;">
            <table class="table table-bordered table-sm" style="font-size:12px;">
                <thead style="background:#f0f0f0;position:sticky;top:0;">
                    <tr>
                        <th style="width:30px;"></th>
                        <th style="text-align:center;">#</th>
                        <th>Date</th>
                        <th>Sales Order</th>
                        <th>Customer</th>
                        <th style="text-align:center;">Boxes</th>
                        <th style="text-align:center;">SKU</th>
                    </tr>
                </thead>
                <tbody>${rows}</tbody>
                <tfoot style="background:#f9f9f9;font-weight:bold;">
                    <tr>
                        <td colspan="5" style="text-align:right;padding:6px 10px;">Totals:</td>
                        <td style="text-align:center;color:green;padding:6px;">${total_boxes}</td>
                        <td style="text-align:center;padding:6px;">${total_sku}</td>
                    </tr>
                </tfoot>
            </table>
        </div>
        <div style="margin-top:6px;font-size:12px;color:#888;text-align:right;">
            <b>${items.length}</b> customer(s) added
        </div>
    `);

    // Bind remove buttons
    dialog.fields_dict.items_html.$wrapper.find(".remove-item").on("click", function() {
        let idx = parseInt($(this).data("idx"));
        items.splice(idx, 1);
        render_items_table(dialog, items);
    });
}

// Create gate pass doc and stamp gate pass name on each linked sales order
function create_gate_pass(dialog, values, items) {
    if (items.length === 0) {
        frappe.msgprint({
            title: "No Customers Added",
            indicator: "orange",
            message: "Please add at least one customer."
        });
        return;
    }

    // Build gate pass child table rows
    let gate_pass_items = items.map(item => ({
        doctype:     "Gate Pass Item",
        date:        item.date,
        sales_order: item.so,
        customer:    item.customer,
        no_of_boxes: item.boxes,
        no_of_sku:   item.sku
    }));

    // Show saving state in dialog
    dialog.fields_dict.items_html.$wrapper.html(`
        <div style="text-align:center;padding:30px;color:#888;">
            Saving Gate Pass...
        </div>
    `);

    frappe.call({
        method: "frappe.client.insert",
        args: {
            doc: {
                doctype:     "Gate Pass",
                date:        frappe.datetime.get_today(),
                driver_name: values.driver_name || "",
                vehicle_no:  values.vehicle_no  || "",
                mileage:     values.mileage      || "",
                table_zcvy:  gate_pass_items
            }
        },
        freeze: true,
        freeze_message: "Saving Gate Pass...",
        callback: function(r) {
            if (r.message) {
                let gate_pass_name = r.message.name;

                // Collect valid sales order names
                let sales_orders = items
                    .map(item => item.so)
                    .filter(so => so);

                if (sales_orders.length === 0) {
                    // No sales orders to stamp, just redirect
                    dialog.hide();
                    frappe.show_alert({
                        message: `Gate Pass ${gate_pass_name} created!`,
                        indicator: "green"
                    });
                    frappe.set_route("Form", "Gate Pass", gate_pass_name);
                    return;
                }

                // Stamp gate pass name on each linked sales order
                let promises = sales_orders.map(so => {
                    return frappe.call({
                        method: "frappe.client.set_value",
                        args: {
                            doctype:   "Sales Order",
                            name:      so,
                            fieldname: "gate_pass",
                            value:     gate_pass_name
                        }
                    });
                });

                // After all updates done redirect to gate pass form
                Promise.all(promises).then(() => {
                    dialog.hide();
                    frappe.show_alert({
                        message: `Gate Pass ${gate_pass_name} created and linked to ${sales_orders.length} Sales Order(s)!`,
                        indicator: "green"
                    });
                    frappe.set_route("Form", "Gate Pass", gate_pass_name);
                });
            }
        },
        error: function(err) {
            // Show error in dialog
            dialog.fields_dict.items_html.$wrapper.html(`
                <div class="alert alert-danger"
                     style="margin-top:10px;text-align:center;">
                    Failed to save Gate Pass.
                    <br>
                    <small>${err.message || "Unknown error"}</small>
                </div>
            `);
            frappe.msgprint({
                title: "Error",
                indicator: "red",
                message: `Failed to save: ${err.message || "Unknown error"}`
            });
        }
    });
}