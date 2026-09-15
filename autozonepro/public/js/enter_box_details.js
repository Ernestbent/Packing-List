// Packing List — Client Script

// Box item code map keyed by Box Type select value
// box_item_code is stored in custom_box_summary for reporting purposes
const BOX_ITEM_MAP = {
    "3 PLY": "3 PLY. 585*385*420 MM = BROWN = 425GSM = PLAIN = GLUE TYPE",
    "5 PLY": "5 PLY. 585*385*420 MM = BROWN = 730GSM = PLAIN = GLUE TYPE",
    "Company Box": ""
};

frappe.ui.form.on('Packing List', {
    refresh(frm) {
        show_pack_button(frm);
        update_totals(frm);
    },

    custom_pick_list(frm) {
        return load_pl_items(frm);
    },

    before_submit(frm) {
        update_totals(frm);
        const missing = get_missing_items(frm);
        if (missing.length) {
            frappe.msgprint({
                title: __("Cannot Submit – Items Missing"),
                message: __("The following items are not fully packed:<br><ul><li>{0}</li></ul>", [
                    missing.map(m => `${frappe.utils.escape_html(m.item_name)} (Need ${m.need}, Packed ${m.packed})`).join('</li><li>')
                ]),
                indicator: "red"
            });
            frappe.validated = false;
        }
    }
});

frappe.ui.form.on('Packaging Details', {
    quantity(frm) {
        update_totals(frm);
    },
    table_hqkk_remove(frm) {
        update_totals(frm);
    }
});


// --- Button Visibility ---

function show_pack_button(frm) {
    frm.remove_custom_button(__('Pack Items'));

    const should_show = !frm._packing_loading && frm.doc.custom_pick_list &&
        frm.doc.docstatus === 0 &&
        frm.doc.table_ttya &&
        frm.doc.table_ttya.length > 0;

    if (should_show) {
        frm.add_custom_button(__('Pack Items'), () => open_pack_dialog(frm));
    }
}


// --- Load Pick List Items into table_ttya ---

async function load_pl_items(frm) {
    const pick_list = frm.doc.custom_pick_list;
    const request = (frm._packing_load_request || 0) + 1;
    frm._packing_load_request = request;
    frm._packing_loading = true;
    frm.clear_table('table_ttya');
    frm.clear_table('table_hqkk');
    frm.clear_table('custom_box_summary');
    await frm.set_value({custom_customer: '', custom_sales_order: ''});
    frm.refresh_fields();
    show_pack_button(frm);
    update_totals(frm);

    try {
        if (!pick_list) return;
        const pl = await frappe.db.get_doc('Pick List', pick_list);
        if (frm._packing_load_request !== request || frm.doc.custom_pick_list !== pick_list) return;
        if (!pl.locations || !pl.locations.length) {
            frappe.msgprint(__('No items found in this Pick List. Please click "Get Item Locations" on the Pick List first.'));
            return;
        }
        pl.locations.forEach(loc => {
            const row = frm.add_child('table_ttya');
            row.item = loc.item_code;
            row.item_name = loc.item_name;
            row.qty = loc.qty;
            row.uom = loc.uom;
        });
        await frm.set_value({
            custom_customer: pl.customer || '',
            custom_sales_order: pl.locations[0].sales_order || ''
        });
        frm.refresh_field('table_ttya');
    } finally {
        if (frm._packing_load_request === request) {
            frm._packing_loading = false;
            show_pack_button(frm);
            update_totals(frm);
        }
    }
}


// --- Open Pack Dialog ---

function open_pack_dialog(frm) {
    const next_box = get_missing_items(frm).length
        ? get_next_box_number(frm)
        : Math.max(1, get_next_box_number(frm) - 1);

    const d = new frappe.ui.Dialog({
        title: __('Pack Items into Boxes'),
        size: 'large',
        fields: [
            {
                // Box type dropdown — maps to item code stored for reporting
                fieldname: 'box_type',
                fieldtype: 'Select',
                label: __('Box Type'),
                reqd: 1,
                options: '\n3 PLY\n5 PLY\nCompany Box'
            },
            {
                fieldname: 'box_number',
                fieldtype: 'Int',
                label: __('Box Number'),
                reqd: 1,
                default: next_box
            },
            {
                fieldname: 'box_weight',
                fieldtype: 'Float',
                label: __('Box Weight (kg)'),
                reqd: 1,
                default: 0
            },
            {
                fieldname: 'section_break',
                fieldtype: 'Section Break',
                label: __('Select Items for This Box')
            },
            {
                fieldname: 'search_container',
                fieldtype: 'HTML'
            },
            {
                fieldname: 'items_html',
                fieldtype: 'HTML'
            }
        ],
        primary_action_label: __('Save Box'),
        secondary_action_label: __('Close'),

        async primary_action(values) {
            if (d._saving) return;
            const selected = get_selected_items(d);
            if (!save_box(frm, values.box_number, values.box_weight, values.box_type, selected)) return;

            d._saving = true;
            d.get_primary_btn().prop('disabled', true);
            try {
                await frm.save('Save', null, null, () => {});
                // Only advance after the server has accepted the box.
                if (frm.is_dirty()) return;
                if (get_missing_items(frm).length === 0) {
                    d.hide(true);
                    frappe.msgprint({
                        title: __('All Items Packed!'),
                        message: __('All items have been packed. The last box has been saved.'),
                        indicator: 'green'
                    });
                    return;
                }
                if (!d.$wrapper.is(':visible')) return;
                d.fields_dict.search_container.$wrapper.find('#item-search-input').val('');
                await d.set_value('box_number', get_next_box_number(frm));
                load_box_data(frm, d, d.get_value('box_number'));
            } catch (error) {
                // Keep the current box and quantities available for correction/retry.
                frappe.msgprint(__('The box could not be saved. Please correct any errors and try again.'));
            } finally {
                d._saving = false;
                d.get_primary_btn().prop('disabled', false);
            }
        },

        secondary_action() {
            d.hide(true);
        }
    });

    // Prevent accidental dialog close — only force=true closes it
    const originalHide = d.hide;
    d.hide = function (force) {
        if (force === true) {
            originalHide.call(d);
        }
        // Silently block backdrop/Escape close
    };

    // When box number changes load existing box data into the dialog
    d.fields_dict.box_number.df.onchange = () => {
        const box_number = d.get_value('box_number');
        load_box_data(frm, d, box_number);
    };

    render_search_box(frm, d);
    load_box_data(frm, d, next_box);
    d.show();
}


// --- Load Existing Box Data into Dialog When Box Number Changes ---

function load_box_data(frm, dialog, box_number) {
    const summary = (frm.doc.custom_box_summary || []).find(
        row => Number(row.box_number) === Number(box_number)
    );
    dialog.set_value('box_weight', summary ? summary.weight_kg : 0);
    dialog.set_value('box_type', summary ? summary.box_type || '' : '');
    render_items_with_checkboxes(frm, dialog);
}


// Use persisted item/UOM values, never transient array positions, to count packing.
function packing_item_key(row) {
    return JSON.stringify([row.item || '', row.uom || '']);
}

function get_packing_items(frm) {
    const items = new Map();
    (frm.doc.table_ttya || []).forEach(row => {
        const key = packing_item_key(row);
        if (!items.has(key)) items.set(key, {item: row.item, item_name: row.item_name, uom: row.uom, qty: 0});
        items.get(key).qty += Number(row.qty) || 0;
    });
    return Array.from(items.values());
}

function get_packed_quantities(frm, excluded_box) {
    const packed = new Map();
    (frm.doc.table_hqkk || []).forEach(row => {
        if (excluded_box !== undefined && Number(row.box_number) === Number(excluded_box)) return;
        const key = packing_item_key(row);
        packed.set(key, (packed.get(key) || 0) + (Number(row.quantity) || 0));
    });
    return packed;
}


// --- Render Search Input ---

function render_search_box(frm, dialog) {
    const html = `
        <style>
            .search-wrapper { position: relative; margin-bottom: 15px; }
            .search-input { width: 100%; padding: 10px 40px 10px 15px; border: 1px solid #d1d8dd; border-radius: 4px; font-size: 14px; }
            .search-input:focus { border-color: #2490ef; outline: none; box-shadow: 0 0 0 2px rgba(36,144,239,0.1); }
        </style>
        <div class="search-wrapper">
            <input type="text" id="item-search-input" class="search-input" placeholder="Search items by name or code..." autocomplete="off">
        </div>
    `;

    dialog.fields_dict.search_container.$wrapper.html(html);

    dialog.fields_dict.search_container.$wrapper.find('#item-search-input').on('input', function () {
        filter_items_list(dialog, $(this).val());
    });
}


// --- Filter Visible Item Rows by Search Term ---

function filter_items_list(dialog, search_term) {
    const itemsContainer = dialog.fields_dict.items_html.$wrapper.find('.items-container');
    const rows = itemsContainer.find('.pack-item-row');

    itemsContainer.find('.no-results-filter').remove();

    if (!search_term || search_term.trim() === '') {
        rows.show();
        return;
    }

    const term = search_term.toLowerCase().trim();
    let visible = 0;

    rows.each(function () {
        const row = $(this);
        const code = (row.data('item-code') || '').toString().toLowerCase();
        const name = (row.data('item-name') || '').toString().toLowerCase();
        if (code.includes(term) || name.includes(term)) {
            row.show(); visible++;
        } else {
            row.hide();
        }
    });

    if (visible === 0) {
        itemsContainer.append(`<div class="no-results-filter" style="text-align:center;padding:40px;color:#888;">No items match your search</div>`);
    }
}


// --- Render Item Checkboxes in Dialog ---

function render_items_with_checkboxes(frm, dialog) {
    const items = get_packing_items(frm);
    const current_box = dialog.get_value('box_number');

    const packed_elsewhere = get_packed_quantities(frm, current_box);
    const current_quantities = new Map();
    (frm.doc.table_hqkk || []).filter(row => Number(row.box_number) === Number(current_box)).forEach(row => {
        const key = packing_item_key(row);
        current_quantities.set(key, (current_quantities.get(key) || 0) + (Number(row.quantity) || 0));
    });
    // Keep the selection tied to the rendered item even if source rows are reordered.
    dialog._packing_items = items;

    let html = `
        <style>
            .pack-item-row { padding: 12px; border-bottom: 1px solid #e0e0e0; display: flex; align-items: center; gap: 15px; transition: background-color 0.2s; cursor: pointer; }
            .pack-item-row:hover { background-color: #f8f9fa; }
            .pack-item-row.fully-packed { background-color: #f0f0f0; opacity: 0.6; pointer-events: none; }
            .item-checkbox { width: 20px; height: 20px; cursor: pointer; flex-shrink: 0; }
            .item-checkbox:disabled { cursor: not-allowed; }
            .item-details { flex: 1; min-width: 0; }
            .item-name { font-weight: 600; color: #333; margin-bottom: 4px; }
            .item-code { color: #666; font-size: 0.85em; margin-bottom: 4px; }
            .item-remaining { color: #888; font-size: 0.9em; }
            .item-remaining.zero { color: #28a745; font-weight: 600; }
            .item-remaining.overpacked { color: #c92a2a; font-weight: 600; }
            .qty-input { width: 100px; padding: 6px 10px; border: 1px solid #ccc; border-radius: 4px; font-size: 14px; flex-shrink: 0; }
            .qty-input:focus { border-color: #2490ef; outline: none; box-shadow: 0 0 0 2px rgba(36,144,239,0.1); }
            .items-container { max-height: 400px; overflow-y: auto; border: 1px solid #d1d8dd; border-radius: 4px; padding: 10px; background: white; margin-top: 15px; }
            .no-items-message { text-align: center; padding: 40px; color: #888; }
        </style>
        <div class="items-container">
    `;

    if (!items.length) {
        html += '<div class="no-items-message">No items available to pack</div>';
    } else {
        items.forEach((item, idx) => {

            const key = packing_item_key(item);
            const display_available = Math.max(0, item.qty - (packed_elsewhere.get(key) || 0));
            const current_qty = current_quantities.get(key) || 0;
            const total_packed = (packed_elsewhere.get(key) || 0) + current_qty;
            const fully_packed = total_packed === item.qty;
            const overpacked = total_packed > item.qty;
            const disabled = display_available <= 0 && current_qty <= 0;
            const row_class = disabled && fully_packed ? 'pack-item-row fully-packed' : 'pack-item-row';
            const remaining_class = overpacked ? 'item-remaining overpacked'
                : fully_packed ? 'item-remaining zero' : 'item-remaining';
            const status_text = overpacked
                ? __('Overpacked: {0} packed / {1} required. Correct the quantities in the existing boxes.', [total_packed, item.qty])
                : fully_packed ? (current_qty > 0 ? __('Fully Packed (editing this box)') : __('Fully Packed'))
                : `Available for this box: <strong>${display_available}</strong> / ${item.qty} ${frappe.utils.escape_html(item.uom || '')}`;

            html += `
                <div class="${row_class}"
                     data-row-idx="${idx}"
                     data-item="${frappe.utils.escape_html(item.item || '')}"
                     data-item-code="${frappe.utils.escape_html((item.item || '').toLowerCase())}"
                     data-item-name="${frappe.utils.escape_html((item.item_name || '').toLowerCase())}"
                     onclick="window.toggleCheckboxOnRow(this)">
                    <input type="checkbox" class="item-checkbox" data-row-idx="${idx}" data-max="${display_available}"
                           ${disabled ? 'disabled' : ''} ${current_qty > 0 ? 'checked' : ''}
                           onclick="event.stopPropagation()" onchange="window.toggleQtyInput(this)">
                    <div class="item-details">
                        <div class="item-name">${frappe.utils.escape_html(item.item_name || item.item || '')}</div>
                        <div class="item-code">${frappe.utils.escape_html(item.item || '')}</div>
                        <div class="${remaining_class}">${status_text}</div>
                    </div>
                    <input type="number" class="qty-input" data-row-idx="${idx}" placeholder="Qty"
                           min="1" max="${display_available}" step="1" ${current_qty > 0 ? '' : 'disabled'}
                           value="${current_qty > 0 ? current_qty : ''}"
                           onclick="event.stopPropagation()" style="display:${current_qty > 0 ? 'block' : 'none'};">
                </div>
            `;
        });
    }

    html += '</div>';
    dialog.fields_dict.items_html.$wrapper.html(html);
    filter_items_list(dialog, dialog.fields_dict.search_container.$wrapper.find('#item-search-input').val());

    // Toggle qty input visibility when checkbox state changes
    window.toggleQtyInput = function (checkbox) {
        const qtyInput = checkbox.parentElement.querySelector('.qty-input');
        if (checkbox.checked) {
            qtyInput.style.display = 'block';
            qtyInput.disabled = false;
            qtyInput.value = checkbox.dataset.max;
            setTimeout(() => qtyInput.focus(), 50);
        } else {
            qtyInput.style.display = 'none';
            qtyInput.disabled = true;
            qtyInput.value = '';
        }
    };

    // Row click toggles the checkbox
    window.toggleCheckboxOnRow = function (row) {
        const checkbox = row.querySelector('.item-checkbox');
        if (!checkbox.disabled) {
            checkbox.checked = !checkbox.checked;
            window.toggleQtyInput(checkbox);
        }
    };
}


// --- Get Checked Items and Quantities from Dialog ---

function get_selected_items(dialog) {
    const selected = [];
    const wrapper = dialog.fields_dict.items_html.$wrapper;

    wrapper.find('.item-checkbox:checked').each(function () {
        const checkbox = $(this);
        const rowIdx = checkbox.data('row-idx');
        const qty = Number(wrapper.find(`.qty-input[data-row-idx="${rowIdx}"]`).val());
        selected.push({ ...dialog._packing_items[rowIdx], quantity: qty });
    });

    return selected;
}


// --- Save Box to Child Tables ---

function save_box(frm, box_number, weight, box_type, items) {
    if (!Number.isFinite(weight) || weight <= 0) {
        frappe.msgprint({ title: __('Invalid Weight'), message: __('Please enter a valid box weight.'), indicator: 'red' });
        return false;
    }

    if (!items.length) {
        frappe.msgprint({ title: __('No Items Selected'), message: __('Please select at least one item to pack.'), indicator: 'red' });
        return false;
    }

    if (!Number.isInteger(box_number) || box_number <= 0 || !Object.hasOwn(BOX_ITEM_MAP, box_type)) {
        frappe.msgprint(__('Please enter a positive box number and select a Box Type.'));
        return false;
    }

    const required = new Map(get_packing_items(frm).map(row => [packing_item_key(row), row.qty]));
    const packed_elsewhere = get_packed_quantities(frm, box_number);
    const selected_quantities = new Map();
    for (const item of items) {
        const key = packing_item_key(item);
        if (!required.has(key) || !Number.isInteger(item.quantity) || item.quantity <= 0) {
            frappe.msgprint(__('Please select a valid item and enter a positive whole-number quantity.'));
            return false;
        }
        selected_quantities.set(key, (selected_quantities.get(key) || 0) + item.quantity);
        const available = required.get(key) - (packed_elsewhere.get(key) || 0);
        if (selected_quantities.get(key) > available) {
            frappe.msgprint({
                title: __('Quantity Exceeds Available'),
                message: __('Cannot pack {0} units of {1}. Only {2} available.', [
                    selected_quantities.get(key), frappe.utils.escape_html(item.item), available
                ]),
                indicator: 'red'
            });
            return false;
        }
    }

    // Remove existing rows for this box before re-saving
    frm.doc.table_hqkk = (frm.doc.table_hqkk || []).filter(r => Number(r.box_number) !== Number(box_number));

    items.forEach(item => {
        const row = frm.add_child('table_hqkk');
        row.box_number = box_number;
        row.item = item.item;
        row.item_name = item.item_name;
        row.quantity = item.quantity;
        row.uom = item.uom;
    });

    // Update or create the box summary row for this box number
    let summary = (frm.doc.custom_box_summary || []).find(b => Number(b.box_number) === Number(box_number));
    if (!summary) {
        summary = frm.add_child('custom_box_summary');
        summary.box_number = box_number;
    }
    summary.weight_kg = weight;
    // Store box type and item code — used by the Box Consumption report
    summary.box_type = box_type;
    summary.box_item_code = BOX_ITEM_MAP[box_type] || '';

    frm.doc.table_hqkk.forEach((row, idx) => { row.idx = idx + 1; });
    frm.dirty();
    frm.refresh_field('table_hqkk');
    frm.refresh_field('custom_box_summary');
    update_totals(frm);

    return true;
}


// --- Next Available Box Number ---

function get_next_box_number(frm) {
    const used = (frm.doc.table_hqkk || []).map(r => Number(r.box_number)).filter(n => Number.isInteger(n) && n > 0);
    return used.length ? Math.max(...used) + 1 : 1;
}


// --- Update Total Boxes and Total Qty Header Fields ---

function update_totals(frm) {
    const box_numbers = new Set((frm.doc.table_hqkk || []).map(r => Number(r.box_number)).filter(n => Number.isInteger(n) && n > 0));
    frm.set_value('total_boxes', box_numbers.size);
    frm.set_value('total_qty', (frm.doc.table_hqkk || []).reduce((sum, r) => sum + (Number(r.quantity) || 0), 0));
}


// --- Get Items Not Fully Packed (used in before_submit validation) ---

function get_missing_items(frm) {
    const packed = get_packed_quantities(frm);
    const items = new Map(get_packing_items(frm).map(item => [packing_item_key(item), item]));
    (frm.doc.table_hqkk || []).forEach(row => {
        const key = packing_item_key(row);
        if (!items.has(key)) items.set(key, {item: row.item, uom: row.uom, qty: 0});
    });
    return Array.from(items.values()).filter(item => (packed.get(packing_item_key(item)) || 0) !== item.qty)
        .map(item => ({
            item: item.item,
            item_name: item.item_name || item.item,
            need: item.qty,
            packed: packed.get(packing_item_key(item)) || 0
        }));
}
