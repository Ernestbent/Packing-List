frappe.ui.form.on("Sales Order", {
    before_workflow_action: function (frm) {

        if (frm.selected_workflow_action === "Start Packing") {

            return new Promise((resolve, reject) => {

                frappe.call({
                    method: "autozonepro.autozonepro.custom_scripts.check_packing_lists.validate_packing_list_verified",
                    args: {
                        sales_order: frm.doc.name
                    },
                    freeze: true,
                    freeze_message: __("Checking Packing List verification..."),

                    callback: function (r) {
                        if (!r.exc) {
                            if (r.message.blocked) {
                                frappe.msgprint({
                                    title: __("Packing List Verification"),
                                    indicator: "orange",
                                    message: r.message.message
                                });
                                reject();   
                            } else {
                                resolve();  
                            }
                        } else {
                            frappe.msgprint({
                                title: __("Error"),
                                indicator: "red",
                                message: __("Packing verification check failed.")
                            });
                            reject();
                        }
                    },

                    error: function () {
                        frappe.msgprint({
                            title: __("Error"),
                            indicator: "red",
                            message: __("Packing verification check failed.")
                        });
                        reject();
                    }
                });

            });
        }

    }
});
