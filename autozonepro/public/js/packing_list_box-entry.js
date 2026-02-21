frappe.ui.form.on('Packing List', {
    onload: function(frm) {
        frm.fields_dict['table_hqkk'].grid.get_field('item').get_query = function(doc, cdt, cdn) {
            let invoice_items = frm.doc.table_ttya.map(d => d.item_code);
            return {
                filters: [['name', 'in', invoice_items]]
            };
        }
    }
});