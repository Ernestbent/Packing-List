frappe.ui.form.on("Sales Order", {
    before_workflow_action: function (frm) {
        console.log("Workflow action triggered:", frm.selected_workflow_action, "Current state:", frm.doc.workflow_state);
        
        if (frm.selected_workflow_action === "Mark As Delivered" || frm.doc.workflow_state === "Delivered") {
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
                            method: "autozonepro.custom_scripts.update_dn_date.update_delivery_date",
                            args: {
                                sales_order: frm.doc.name,
                                delivery_date: values.delivery_date,
                                custom_remarks_customer: values.custom_remarks_customer
                            },
                            freeze: true,
                            freeze_message: __("Updating Delivery Date..."),
                            callback: function (r) {
                                frappe.dom.unfreeze();
                                d.get_primary_btn().attr("disabled", false);
                                
                                if (!r.exc) {
                                    frappe.msgprint({
                                        title: "Success",
                                        indicator: "green",
                                        message: `Updated Delivery Notes: ${r.message.join(", ") || "None"}`
                                    });
                                    
                                    d.hide();
                                    resolve();
                                    
                                } else {
                                    frappe.msgprint({
                                        title: "Error",
                                        indicator: "red",
                                        message: `Failed to update Delivery Notes: ${r.exc || "Unknown server error"}.`
                                    });
                                    console.error("Server error response:", r);
                                    reject();
                                }
                            },
                            error: function (err) {
                                frappe.dom.unfreeze();
                                d.get_primary_btn().attr("disabled", false);
                                
                                frappe.msgprint({
                                    title: "Error",
                                    indicator: "red",
                                    message: `An error occurred: ${err.message || "Unknown error"}.`
                                });
                                console.error("Client-side error details:", err);
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
