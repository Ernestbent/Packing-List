// The server blocks the workflow; this helper only opens the optional transfer draft.
frappe.provide('autozonepro');

autozonepro.open_main_location_transfer = function (args) {
    frappe.msg_dialog.hide();
    return frappe.new_doc('Stock Entry', {
        company: args.company,
        stock_entry_type: 'Material Transfer'
    }, function (doc) {
        doc.purpose = 'Material Transfer';
        doc.items = [];
        args.items.forEach(values => {
            const row = frappe.model.add_child(doc, 'Stock Entry Detail', 'items');
            Object.assign(row, values);
        });
    });
};
