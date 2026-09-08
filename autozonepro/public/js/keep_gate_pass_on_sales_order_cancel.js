frappe.ui.form.on("Sales Order", {
	setup(frm) {
		frm.ignore_doctypes_on_cancel_all = [
			...new Set([...(frm.ignore_doctypes_on_cancel_all || []), "Gate Pass"]),
		];
	},
});
