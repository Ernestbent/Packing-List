frappe.ui.form.on('Sales Order', {
    refresh: function(frm) {
        if (frm.doc.docstatus !== 1) return;

        setTimeout(() => {
            ['Work Order', 'Material Request', 'Purchase Order', 'Project', 'Payment Request', 'Request for Raw Materials','Payment'].forEach(label => {
                frm.remove_custom_button(label, 'Create');
                frm.remove_custom_button(label, 'Make');
            });

            frm.add_custom_button(__('Packing List'), function() {
                frappe.call({
                    method: 'frappe.client.get_list',
                    args: {
                        doctype: 'Delivery Note',
                        filters: { docstatus: 1 },
                        or_filters: [
                            ['Delivery Note Item', 'against_sales_order', '=', frm.doc.name]
                        ],
                        fields: ['`tabDelivery Note`.`name`', 'posting_date', 'customer', 'posting_time'],
                        order_by: '`tabDelivery Note`.posting_date desc, `tabDelivery Note`.creation desc',
                        limit_page_length: 1
                    },
                    callback: function(r) {
                        if (!r.message || r.message.length === 0) {
                            frappe.throw(__('Cannot create Packing List.<br><br>No submitted Delivery Note found for Sales Order: <b>{0}</b>', [frm.doc.name]));
                            return;
                        }

                        const dn = r.message[0];

                        frappe.model.with_doctype('Packing List', () => {
                            const pl = frappe.model.get_new_doc('Packing List');

                            pl.custom_sales_order = frm.doc.name;  
                            pl.delivery_note = dn.name;
                            pl.custom_customer = dn.customer;
                            pl.custom_date = dn.posting_date;
                            pl.custom_posting_time = dn.posting_time || frappe.datetime.now_time();

                            frappe.db.get_doc('Delivery Note', dn.name).then(dn_doc => {
                                dn_doc.items.forEach(item => {
                                    const row = frappe.model.add_child(pl, 'table_ttya');
                                    row.item_code = item.item_code;
                                    row.item_name = item.item_name;
                                    row.description = item.description || item.item_name;
                                    row.qty = item.qty;
                                    row.uom = item.uom;
                                    row.rate = item.rate || 0;
                                    row.amount = item.amount || 0;
                                });

                                frappe.set_route('Form', 'Packing List', pl.name);
                            });
                        });
                    }
                });
            }, __('Create'));
        }, 500);
    }
});