frappe.ui.form.on('Sales Order', {
    refresh: function(frm) {
        if (frm.doc.docstatus !== 1) return;

        setTimeout(() => {
            // Remove unwanted default buttons
            ['Work Order', 'Material Request', 'Purchase Order', 'Project', 'Payment Request', 'Request for Raw Materials', 'Payment'].forEach(label => {
                frm.remove_custom_button(label, 'Create');
                frm.remove_custom_button(label, 'Make');
            });

            // Reset our controlled buttons first, then add back only when allowed
            frm.remove_custom_button('Pick List', 'Create');
            frm.remove_custom_button('Pick List', 'Make');
            frm.remove_custom_button('Packing List', 'Create');
            frm.remove_custom_button('Packing List', 'Make');
            frm.remove_custom_button('Packing List');

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
                        frm.remove_custom_button('Pick List', 'Create');
                        frm.remove_custom_button('Pick List', 'Make');
                        return;
                    }

                    if (frm.doc.workflow_state === 'Picking') {
                        frm.add_custom_button(__('Pick List'), function() {
                            frappe.model.open_mapped_doc({
                                method: 'erpnext.selling.doctype.sales_order.sales_order.create_pick_list',
                                frm: frm
                            });
                        }, __('Create'));
                    }
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
                        return;
                    }

                    if (frm.doc.workflow_state === 'Packing') {
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
                                        const doc = {
                                            doctype: 'Packing List',
                                            custom_pick_list: pl_doc.name,
                                            custom_sales_order: frm.doc.name,
                                            custom_customer: pl_doc.customer,
                                            custom_date: frappe.datetime.get_today(),
                                            custom_posting_time: frappe.datetime.now_time(),
                                            table_ttya: (pl_doc.locations || []).map(loc => ({
                                                doctype: 'Packing List Item',
                                                item: loc.item_code,
                                                item_name: loc.item_name,
                                                qty: loc.picked_qty,
                                                uom: loc.uom
                                            }))
                                        };

                                        // Insert directly via API — reliable with child tables
                                        frappe.call({
                                            method: 'frappe.client.insert',
                                            args: { doc: doc },
                                            callback: function(r) {
                                                if (r.message) {
                                                    frappe.set_route('Form', 'Packing List', r.message.name);
                                                }
                                            }
                                        });
                                    });
                                }
                            });
                        }, __('Create'));
                    }
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
                        frm.remove_custom_button('Delivery Note', 'Create');
                        frm.remove_custom_button('Delivery Note', 'Make');
                    }
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
                        frm.remove_custom_button('Sales Invoice', 'Create');
                        frm.remove_custom_button('Sales Invoice', 'Make');
                    }
                }
            });

        }, 500);
    }
});
