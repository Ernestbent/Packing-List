// Sales Order client script
// Fires before any workflow action is executed

frappe.ui.form.on("Sales Order", {

    before_workflow_action: function(frm) {

        // Only intercept Start Transit action
        if (frm.doc.workflow_state !== "Billed") return;

        return new Promise((resolve, reject) => {

            // Check Gate Pass Items for this Sales Order today
            frappe.call({
                method: "frappe.client.get_list",
                args: {
                    doctype: "Gate Pass Item",
                    filters: {
                        sales_order: frm.doc.name,  // confirm fieldname
                        docstatus: 1
                    },
                    fields: ["parent"]
                },
                callback: function(r) {

                    if (!r.message || r.message.length === 0) {
                        frappe.msgprint({
                            title: __("Gate Pass Required"),
                            message: __("No submitted Gate Pass found for {0}.", [frm.doc.name]),
                            indicator: "red"
                        });
                        return reject();
                    }

                    // Check if any gate pass is dated today
                    let parents = r.message.map(d => d.parent);
                    let today = frappe.datetime.get_today();

                    frappe.call({
                        method: "frappe.client.get_list",
                        args: {
                            doctype: "Gate Pass",
                            filters: {
                                name: ["in", parents],
                                date: today,
                                docstatus: 1
                            },
                            fields: ["name", "date"]
                        },
                        callback: function(r2) {

                            if (!r2.message || r2.message.length === 0) {
                                frappe.msgprint({
                                    title: __("Gate Pass Required"),
                                    message: __("No Gate Pass found for today ({0}) for Sales Order {1}.", [today, frm.doc.name]),
                                    indicator: "red"
                                });
                                return reject();
                            }

                            // Valid gate pass found, allow transition
                            resolve();
                        }
                    });
                }
            });
        });
    }
});