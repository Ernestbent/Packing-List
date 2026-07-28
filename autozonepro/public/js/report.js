frappe.ui.form.on("Report", {
	refresh(frm) {
		if (frm.is_new() || !frm.doc.prepared_report) {
			return;
		}

		frm.add_custom_button(__("Turn Off Prepared Report"), () => {
			frappe.call({
				method: "autozonepro.autozonepro.utils.report_settings.disable_prepared_report",
				args: {
					report_name: frm.doc.name,
				},
				freeze: true,
				freeze_message: __("Turning off Prepared Report..."),
			}).then(() => frm.reload_doc());
		});
	},
});
