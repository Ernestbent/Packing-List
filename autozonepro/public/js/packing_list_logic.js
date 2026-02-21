frappe.ui.form.on('Packing List', {
    delivery_note: function(frm) {
        // Exit if no Delivery Note selected
        if (!frm.doc.delivery_note) {
            frm.set_value('custom_customer', '');
            frm.clear_table('table_ttya');
            frm.refresh_field('table_ttya');
            return;
        }

        // Fetch Delivery Note with Customer + Items
        frappe.db.get_doc('Delivery Note', frm.doc.delivery_note).then(dn => {
            // === 1. Set Customer ===
            frm.set_value('custom_customer', dn.customer);
            frm.refresh_field('custom_customer');

            // === 2. Fill Items Table ===
            frm.clear_table('table_ttya');
            dn.items.forEach(i => {
                let row = frm.add_child('table_ttya');
                row.item_code = i.item_code;
                row.item_name = i.item_name;
                row.qty = i.qty;
                row.uom = i.uom;
                row.rate = i.rate;
                row.amount = i.amount;
            });
            frm.refresh_field('table_ttya');

            // === Optional: Auto-fill Date & Time ===
            frm.set_value('custom_date', dn.posting_date);
            frm.set_value('custom_posting_time', dn.posting_time);
            frm.refresh_fields(['custom_date', 'custom_posting_time']);

        }).catch(err => {
            frappe.msgprint({
                title: __('Error'),
                message: __('Failed to fetch Delivery Note: ') + err.message,
                indicator: 'red'
            });
        });
    }
});