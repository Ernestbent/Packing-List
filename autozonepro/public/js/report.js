const reports_with_prepared_report_disabled = new Set([
	"General Ledger",
	"Trial Balance",
	"Accounts Receivable",
	"Accounts Payable",
	"Balance Sheet",
	"Profit and Loss Statement",
	"Stock Ledger",
	"Stock Balance",
]);

frappe.ui.form.on("Report", {
	refresh(frm) {
		if (
			frm.is_new() ||
			!frm.doc.prepared_report ||
			!reports_with_prepared_report_disabled.has(frm.doc.name)
		) {
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
