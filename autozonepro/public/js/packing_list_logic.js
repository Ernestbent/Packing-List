frappe.ui.form.on('Packing List', {
    refresh: function(frm) {
        if (frm.doc.custom_pick_list && (!frm.doc.table_ttya || !frm.doc.table_ttya.length)) {
            load_pl_items(frm);
        }
    },
    custom_pick_list: function(frm) {
        if (!frm.doc.custom_pick_list) {
            frm.set_value('custom_customer', '');
            frm.clear_table('table_ttya');
            frm.refresh_field('table_ttya');
            return;
        }
        load_pl_items(frm);
    }
});

function load_pl_items(frm) {
    frappe.db.get_doc('Pick List', frm.doc.custom_pick_list)
    .then(function(pl) {
        if (!pl.locations || pl.locations.length === 0) {
            frappe.msgprint(__('This Pick List has no items. Please click "Get Item Locations" on the Pick List first.'));
            return;
        }

        frm.clear_table('table_ttya');

        pl.locations.forEach(function(loc) {
            let row = frm.add_child('table_ttya');
            row.item = loc.item_code;
            row.item_name = loc.item_name;
            row.qty = loc.picked_qty; 
            row.uom = loc.uom;
        });

        frm.refresh_field('table_ttya');

        // Set customer separately after table
        frappe.db.get_value('Pick List', frm.doc.custom_pick_list, 'customer')
        .then(function(r) {
            if (r.message && r.message.customer) {
                frm.set_value('custom_customer', r.message.customer);
            }
        });
    });
}