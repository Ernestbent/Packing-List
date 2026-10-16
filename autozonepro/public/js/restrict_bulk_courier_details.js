frappe.after_ajax(() => {
    const existing_settings = frappe.listview_settings["Sales Order"] || {};
    const existing_onload = existing_settings.onload;

    frappe.listview_settings["Sales Order"] = Object.assign(existing_settings, {
        onload(listview) {
            if (existing_onload) {
                existing_onload.call(this, listview);
            }

            const courier_action = listview.workflow_action_items?.["Enter Courier Details"];
            if (!courier_action) return;

            courier_action.off("click").on("click", (event) => {
                event.preventDefault();
                event.stopImmediatePropagation();
                frappe.msgprint({
                    title: __("Action Not Allowed"),
                    indicator: "red",
                    message: __("Enter Courier Details cannot be used as a bulk workflow action. Please process each Sales Order separately."),
                });
            });
        },
    });
});
