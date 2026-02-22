frappe.ui.form.on('Sales Order', {
    refresh: function(frm) {
        if (frm.doc.docstatus !== 1) return;

        setTimeout(() => {
            // Remove unwanted default buttons
            ['Work Order', 'Material Request', 'Purchase Order', 'Project', 'Payment Request', 'Request for Raw Materials', 'Payment'].forEach(label => {
                frm.remove_custom_button(label, 'Create');
                frm.remove_custom_button(label, 'Make');
            });

            // ── 1. PICK LIST ──
            frappe.call({
                method: 'frappe.client.get_list',
                args: {
                    doctype: 'Pick List',
                    filters: [
                        ['Pick List Item', 'sales_order', '=', frm.doc.name],
                        ['docstatus', '!=', 2]
                    ],
                    fields: ['name'],
                    order_by: '`tabPick List`.creation desc',
                    limit_page_length: 1
                },
                callback: function(r) {
                    if (r.message && r.message.length > 0) {
                        // Active Pick List exists — remove Create button
                        frm.remove_custom_button('Pick List', 'Create');
                        frm.remove_custom_button('Pick List', 'Make');
                    }
                    // Cancelled or none — ERPNext shows Create natively
                }
            });

            // ── 2. PACKING LIST ──
            frappe.call({
                method: 'frappe.client.get_list',
                args: {
                    doctype: 'Packing List',
                    filters: [
                        ['custom_sales_order', '=', frm.doc.name],
                        ['docstatus', '!=', 2]
                    ],
                    fields: ['name'],
                    order_by: '`tabPacking List`.creation desc',
                    limit_page_length: 1
                },
                callback: function(r) {
                    if (r.message && r.message.length > 0) {
                        // Active Packing List exists — don't show Create
                        return;
                    }
                    // No active Packing List — show Create button
                    frm.add_custom_button(__('Packing List'), function() {
                        frappe.call({
                            method: 'frappe.client.get_list',
                            args: {
                                doctype: 'Pick List',
                                filters: [
                                    ['Pick List Item', 'sales_order', '=', frm.doc.name],
                                    ['docstatus', '!=', 2]
                                ],
                                fields: ['name', 'customer', 'docstatus'],
                                order_by: '`tabPick List`.creation desc',
                                limit_page_length: 1
                            },
                            callback: function(pick_r) {
                                if (!pick_r.message || pick_r.message.length === 0) {
                                    frappe.throw(__('No Pick List found for Sales Order: <b>{0}</b>', [frm.doc.name]));
                                    return;
                                }

                                const pl_name = pick_r.message[0].name;

                                frappe.db.get_doc('Pick List', pl_name).then(pl_doc => {
                                    frappe.model.with_doctype('Packing List', () => {
                                        const new_pl = frappe.model.get_new_doc('Packing List');
                                        new_pl.custom_pick_list = pl_doc.name;
                                        new_pl.custom_sales_order = frm.doc.name;
                                        new_pl.custom_customer = pl_doc.customer;
                                        new_pl.custom_date = frappe.datetime.get_today();
                                        new_pl.custom_posting_time = frappe.datetime.now_time();

                                        (pl_doc.locations || []).forEach(loc => {
                                            const row = frappe.model.add_child(new_pl, 'Items', 'table_ttya');
                                            row.item = loc.item_code;
                                            row.item_name = loc.item_name;
                                            row.qty = loc.qty;
                                            row.uom = loc.uom;
                                        });

                                        frappe.set_route('Form', 'Packing List', new_pl.name);
                                    });
                                });
                            }
                        });
                    }, __('Create'));
                }
            });

            // ── 3. DELIVERY NOTE ──
            frappe.call({
                method: 'frappe.client.get_list',
                args: {
                    doctype: 'Delivery Note',
                    filters: [
                        ['Delivery Note Item', 'against_sales_order', '=', frm.doc.name],
                        ['docstatus', '!=', 2]
                    ],
                    fields: ['name'],
                    order_by: '`tabDelivery Note`.creation desc',
                    limit_page_length: 1
                },
                callback: function(r) {
                    if (r.message && r.message.length > 0) {
                        // Active Delivery Note exists — remove Create button
                        frm.remove_custom_button('Delivery Note', 'Create');
                        frm.remove_custom_button('Delivery Note', 'Make');
                    }
                    // Cancelled or none — ERPNext shows Create natively
                }
            });

            // ── 4. SALES INVOICE ──
            frappe.call({
                method: 'frappe.client.get_list',
                args: {
                    doctype: 'Sales Invoice',
                    filters: [
                        ['Sales Invoice Item', 'sales_order', '=', frm.doc.name],
                        ['docstatus', '!=', 2]
                    ],
                    fields: ['name'],
                    order_by: '`tabSales Invoice`.creation desc',
                    limit_page_length: 1
                },
                callback: function(r) {
                    if (r.message && r.message.length > 0) {
                        // Active Sales Invoice exists — remove Create button
                        frm.remove_custom_button('Sales Invoice', 'Create');
                        frm.remove_custom_button('Sales Invoice', 'Make');
                    }
                    // Cancelled or none — ERPNext shows Create natively
                }
            });

        }, 500);
    }
});