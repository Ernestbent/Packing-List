frappe.ui.form.on('Pick List', {
    refresh: function(frm) {
        if (frm.doc.docstatus === 1) {
            frm.add_custom_button(__('Packing List'), function() {
                frappe.new_doc('Packing List', {
                    custom_pick_list: frm.doc.name
                });
            }, __('Create'));
        }
    }
});