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
        if (frm.doc.custom_pick_list) {
            load_pl_items(frm);
        } else {
            // Clear all child tables and linked fields when Pick List is removed
            frm.clear_table('table_ttya');
            frm.clear_table('table_hqkk');
            frm.clear_table('custom_box_summary');
            frm.set_value('custom_customer', '');
            frm.refresh_fields();
        }
        show_pack_button(frm);
        update_totals(frm);
    },

    before_submit(frm) {
        update_totals(frm);
        const missing = get_missing_items(frm);
        if (missing.length) {
            frappe.msgprint({
                title: __("Cannot Submit – Items Missing"),
                message: __("The following items are not fully packed:<br><ul><li>{0}</li></ul>", [
                    missing.map(m => `${m.item_name} (Need ${m.need}, Packed ${m.packed})`).join('</li><li>')
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

    const should_show = frm.doc.custom_pick_list &&
        frm.doc.docstatus === 0 &&
        frm.doc.table_ttya &&
        frm.doc.table_ttya.length > 0;

    if (should_show) {
        frm.add_custom_button(__('Pack Items'), () => open_pack_dialog(frm));
    }
}


// --- Load Pick List Items into table_ttya ---

function load_pl_items(frm) {
    if (!frm.doc.custom_pick_list) return;

    frappe.db.get_doc('Pick List', frm.doc.custom_pick_list)
        .then(function (pl) {
            if (!pl.locations || !pl.locations.length) {
                frappe.msgprint(__('No items found in this Pick List. Please click "Get Item Locations" on the Pick List first.'));
                return;
            }

            frm.clear_table('table_ttya');

            pl.locations.forEach(function (loc) {
                const row = frm.add_child('table_ttya');
                row.item = loc.item_code;
                row.item_name = loc.item_name;
                row.qty = loc.qty;
                row.uom = loc.uom;
            });

            frm.refresh_field('table_ttya');

            if (pl.customer) frm.set_value('custom_customer', pl.customer);

            if (pl.locations[0] && pl.locations[0].sales_order) {
                frm.set_value('custom_sales_order', pl.locations[0].sales_order);
            }

            show_pack_button(frm);
            update_totals(frm);
        });
}


// --- Open Pack Dialog ---

function open_pack_dialog(frm) {
    const next_box = get_next_box_number(frm);

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
        primary_action_label: __('Save Box & Continue'),
        secondary_action_label: __('Close'),

        primary_action(values) {
            if (!values.box_type) {
                frappe.msgprint({
                    title: __('Box Type Required'),
                    message: __('Please select a Box Type before saving.'),
                    indicator: 'red'
                });
                return;
            }

            const selected = get_selected_items(d);

            if (save_box(frm, values.box_number, values.box_weight, values.box_type, selected)) {
                frm.save().then(() => {
                    setTimeout(() => {
                        if (d && d.$wrapper && d.$wrapper.is(':visible')) {
                            const next_box_num = values.box_number + 1;

                            // Reset search input for the next box
                            const searchInput = d.fields_dict.search_container.$wrapper.find('#item-search-input');
                            if (searchInput.length) searchInput.val('');

                            clear_all_selections(d);

                            d.set_value('box_type', '');
                            d.set_value('box_number', next_box_num);
                            d.set_value('box_weight', 0);

                            render_items_with_checkboxes(frm, d);
                            d.$wrapper.css('z-index', '1060');
                            d.show();

                            // Notify when all items are fully packed
                            const missing = get_missing_items(frm);
                            if (missing.length === 0) {
                                frappe.msgprint({
                                    title: __('All Items Packed!'),
                                    message: __('All items from the Pick List have been packed. You can close the dialog now.'),
                                    indicator: 'green'
                                });
                            }
                        }
                    }, 200);
                });
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
    render_items_with_checkboxes(frm, d);
    d.show();
}


// --- Load Existing Box Data into Dialog When Box Number Changes ---

function load_box_data(frm, dialog, box_number) {
    const existing_items = (frm.doc.table_hqkk || []).filter(r => r.box_number === box_number);

    if (existing_items.length > 0) {
        const box_summary = (frm.doc.custom_box_summary || []).find(b => b.box_number === box_number);

        if (box_summary) {
            dialog.set_value('box_weight', box_summary.weight_kg || 0);
            // Restore the saved box type for this box
            dialog.set_value('box_type', box_summary.box_type || '');
        }

        setTimeout(() => {
            render_items_with_checkboxes(frm, dialog);

            existing_items.forEach(box_item => {
                let row_idx = box_item.source_row_idx;

                // Fallback: match by item code occurrence if source_row_idx is missing
                if (row_idx === undefined || row_idx === null) {
                    let item_occurrence = 0;
                    for (let i = 0; i < frm.doc.table_hqkk.length; i++) {
                        if (frm.doc.table_hqkk[i].item === box_item.item && frm.doc.table_hqkk[i].box_number === box_number) {
                            if (frm.doc.table_hqkk[i].name === box_item.name) break;
                            item_occurrence++;
                        }
                    }

                    let occurrence_count = 0;
                    for (let i = 0; i < frm.doc.table_ttya.length; i++) {
                        if (frm.doc.table_ttya[i].item === box_item.item) {
                            if (occurrence_count === item_occurrence) { row_idx = i; break; }
                            occurrence_count++;
                        }
                    }
                }

                if (row_idx !== null && row_idx !== undefined) {
                    const checkbox = dialog.fields_dict.items_html.$wrapper.find(`.item-checkbox[data-row-idx="${row_idx}"]`);
                    if (checkbox.length) {
                        checkbox.prop('checked', true);
                        const qtyInput = checkbox.closest('.pack-item-row').find('.qty-input');
                        qtyInput.show().prop('disabled', false).val(box_item.quantity);
                    }
                }
            });
        }, 100);

    } else {
        dialog.set_value('box_weight', 0);
        dialog.set_value('box_type', '');
        clear_all_selections(dialog);
        render_items_with_checkboxes(frm, dialog);
    }
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
    const items = frm.doc.table_ttya || [];
    const current_box = dialog.get_value('box_number');

    const has_source_row_idx = (frm.doc.table_hqkk || []).some(
        r => r.source_row_idx !== undefined && r.source_row_idx !== null
    );

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

            // Total packed across all boxes for this row
            let total_packed = 0;
            (frm.doc.table_hqkk || []).forEach(box_item => {
                const match = has_source_row_idx
                    ? box_item.source_row_idx === idx
                    : box_item.item === item.item;
                if (match) total_packed += (box_item.quantity || 0);
            });

            const remaining = Math.max(0, item.qty - total_packed);

            // Add back current box quantity for display purposes
            let display_remaining = remaining;
            (frm.doc.table_hqkk || []).forEach(box_item => {
                if (box_item.box_number !== current_box) return;
                const match = has_source_row_idx
                    ? box_item.source_row_idx === idx
                    : box_item.item === item.item;
                if (match) display_remaining += (box_item.quantity || 0);
            });

            // Check if this item is already saved in the current box
            const is_in_current_box = (frm.doc.table_hqkk || []).some(
                b => b.box_number === current_box && b.source_row_idx === idx
            );

            const display_available = is_in_current_box
                ? ((frm.doc.table_hqkk || []).find(
                    b => b.box_number === current_box && b.source_row_idx === idx
                ) || {}).quantity || 0
                : display_remaining;

            // Packed in other boxes — determines whether to grey out this row
            let packed_elsewhere = 0;
            (frm.doc.table_hqkk || []).forEach(box_item => {
                if (box_item.box_number === current_box) return;
                const match = has_source_row_idx
                    ? box_item.source_row_idx === idx
                    : box_item.item === item.item;
                if (match) packed_elsewhere += (box_item.quantity || 0);
            });

            const is_fully_packed_elsewhere = packed_elsewhere >= item.qty;

            let disabled, row_class, remaining_class, status_text;

            if (is_in_current_box) {
                // Item exists in this box — always editable
                disabled = false;
                row_class = 'pack-item-row';
                remaining_class = 'item-remaining';
                status_text = `Editing: Packed <strong>${display_available}</strong> in this box`;
            } else if (is_fully_packed_elsewhere) {
                // Fully packed in other boxes — disable and grey out
                disabled = true;
                row_class = 'pack-item-row fully-packed';
                remaining_class = 'item-remaining zero';
                status_text = 'Fully Packed';
            } else {
                // Available to pack in this box
                disabled = false;
                row_class = 'pack-item-row';
                remaining_class = 'item-remaining';
                status_text = `Available: <strong>${display_available}</strong> / ${item.qty} ${item.uom || ''}`;
            }

            html += `
                <div class="${row_class}"
                     data-row-idx="${idx}"
                     data-item="${item.item}"
                     data-item-code="${item.item.toLowerCase()}"
                     data-item-name="${(item.item_name || '').toLowerCase()}"
                     onclick="window.toggleCheckboxOnRow(this)">
                    <input type="checkbox" class="item-checkbox" data-row-idx="${idx}" data-max="${display_available}"
                           ${disabled ? 'disabled' : ''}
                           onclick="event.stopPropagation()" onchange="window.toggleQtyInput(this)">
                    <div class="item-details">
                        <div class="item-name">${item.item_name || item.item}</div>
                        <div class="item-code">${item.item}</div>
                        <div class="${remaining_class}">${status_text}</div>
                    </div>
                    <input type="number" class="qty-input" data-row-idx="${idx}" placeholder="Qty"
                           min="1" max="${display_available}" step="1" disabled
                           onclick="event.stopPropagation()" style="display:none;">
                </div>
            `;
        });
    }

    html += '</div>';
    dialog.fields_dict.items_html.$wrapper.html(html);

    // Auto-check items already saved in the current box
    setTimeout(() => {
        (frm.doc.table_hqkk || []).filter(r => r.box_number === current_box).forEach(boxItem => {
            const checkbox = dialog.fields_dict.items_html.$wrapper.find(`.item-checkbox[data-row-idx="${boxItem.source_row_idx}"]`);
            if (checkbox.length) {
                checkbox.prop('checked', true);
                const qtyInput = checkbox.closest('.pack-item-row').find('.qty-input');
                qtyInput.show().prop('disabled', false).val(boxItem.quantity);
            }
        });
    }, 100);

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


// --- Clear All Checkbox Selections in Dialog ---

function clear_all_selections(dialog) {
    const wrapper = dialog.fields_dict.items_html.$wrapper;
    wrapper.find('.item-checkbox:checked').each(function () {
        $(this).prop('checked', false);
        const qtyInput = $(this).closest('.pack-item-row').find('.qty-input');
        qtyInput.hide().prop('disabled', true).val('');
    });
}


// --- Get Checked Items and Quantities from Dialog ---

function get_selected_items(dialog) {
    const selected = [];
    const wrapper = dialog.fields_dict.items_html.$wrapper;

    wrapper.find('.item-checkbox:checked').each(function () {
        const checkbox = $(this);
        const rowIdx = checkbox.data('row-idx');
        const qty = parseFloat(wrapper.find(`.qty-input[data-row-idx="${rowIdx}"]`).val()) || 0;
        if (qty > 0) selected.push({ row_idx: rowIdx, quantity: qty });
    });

    return selected;
}


// --- Save Box to Child Tables ---

function save_box(frm, box_number, weight, box_type, items) {
    if (!weight || weight <= 0) {
        frappe.msgprint({ title: __('Invalid Weight'), message: __('Please enter a valid box weight.'), indicator: 'red' });
        return false;
    }

    if (!items.length) {
        frappe.msgprint({ title: __('No Items Selected'), message: __('Please select at least one item to pack.'), indicator: 'red' });
        return false;
    }

    const has_source_row_idx = (frm.doc.table_hqkk || []).some(
        r => r.source_row_idx !== undefined && r.source_row_idx !== null
    );

    // Validate each item quantity against what is still available
    for (const item of items) {
        const row = frm.doc.table_ttya[item.row_idx];
        if (!row) continue;

        let packed_elsewhere = 0;
        (frm.doc.table_hqkk || []).forEach(box_item => {
            if (box_item.box_number === box_number) return;
            const match = has_source_row_idx
                ? box_item.source_row_idx === item.row_idx
                : box_item.item === row.item;
            if (match) packed_elsewhere += (box_item.quantity || 0);
        });

        const available = row.qty - packed_elsewhere;

        if (item.quantity > available) {
            frappe.msgprint({
                title: __('Quantity Exceeds Available'),
                message: __('Cannot pack {0} units of {1}. Only {2} available.', [item.quantity, row.item, available]),
                indicator: 'red'
            });
            return false;
        }
    }

    // Remove existing rows for this box before re-saving
    frm.doc.table_hqkk = (frm.doc.table_hqkk || []).filter(r => r.box_number !== box_number);

    items.forEach(item => {
        const row_item = frm.doc.table_ttya[item.row_idx];
        const row = frm.add_child('table_hqkk');
        row.box_number = box_number;
        row.item = row_item.item;
        row.item_name = row_item.item_name;
        row.quantity = item.quantity;
        row.box_weight = weight;
        row.uom = row_item.uom;
        row.source_row_idx = item.row_idx;
    });

    // Update or create the box summary row for this box number
    let summary = (frm.doc.custom_box_summary || []).find(b => b.box_number === box_number);
    if (!summary) {
        summary = frm.add_child('custom_box_summary');
        summary.box_number = box_number;
    }
    summary.weight_kg = weight;
    // Store box type and item code — used by the Box Consumption report
    summary.box_type = box_type;
    summary.box_item_code = BOX_ITEM_MAP[box_type] || '';

    frm.refresh_field('table_hqkk');
    frm.refresh_field('custom_box_summary');
    update_totals(frm);

    return true;
}


// --- Packed Qty Per Source Row Index (fallback-safe) ---

function calculate_packed_qty_by_row(frm) {
    const packed = {};

    (frm.doc.table_hqkk || []).forEach(row => {
        let source_idx = row.source_row_idx;

        // Fallback: derive source index by item code occurrence order
        if (source_idx === undefined || source_idx === null) {
            const item_code = row.item;
            let occurrence = 0;

            for (let i = 0; i < frm.doc.table_hqkk.length; i++) {
                if (frm.doc.table_hqkk[i].item === item_code) {
                    if (i === frm.doc.table_hqkk.indexOf(row)) break;
                    occurrence++;
                }
            }

            let matched_count = 0;
            for (let i = 0; i < frm.doc.table_ttya.length; i++) {
                if (frm.doc.table_ttya[i].item === item_code) {
                    if (matched_count === occurrence) { source_idx = i; break; }
                    matched_count++;
                }
            }
        }

        if (source_idx !== undefined && source_idx !== null) {
            packed[source_idx] = (packed[source_idx] || 0) + (row.quantity || 0);
        }
    });

    return packed;
}


// --- Next Available Box Number ---

function get_next_box_number(frm) {
    const used = (frm.doc.table_hqkk || []).map(r => r.box_number).filter(Boolean);
    return used.length ? Math.max(...used) + 1 : 1;
}


// --- Update Total Boxes and Total Qty Header Fields ---

function update_totals(frm) {
    const box_numbers = new Set((frm.doc.table_hqkk || []).map(r => r.box_number).filter(Boolean));
    frm.set_value('total_boxes', box_numbers.size);
    frm.set_value('total_qty', (frm.doc.table_hqkk || []).reduce((sum, r) => sum + (r.quantity || 0), 0));
}


// --- Get Items Not Fully Packed (used in before_submit validation) ---

function get_missing_items(frm) {
    const missing = [];
    const has_source_row_idx = (frm.doc.table_hqkk || []).some(
        r => r.source_row_idx !== undefined && r.source_row_idx !== null
    );

    if (!has_source_row_idx && frm.doc.table_hqkk && frm.doc.table_hqkk.length > 0) {
        // Legacy path: match by item code only
        const packed_by_item = {};
        (frm.doc.table_hqkk || []).forEach(row => {
            packed_by_item[row.item] = (packed_by_item[row.item] || 0) + (row.quantity || 0);
        });

        (frm.doc.table_ttya || []).forEach(inv => {
            const packed_qty = packed_by_item[inv.item] || 0;
            if (packed_qty < inv.qty) {
                missing.push({ item: inv.item, item_name: inv.item_name || inv.item, need: inv.qty, packed: packed_qty });
            }
        });

    } else {
        // Preferred path: match by source row index
        const packed_by_row = calculate_packed_qty_by_row(frm);

        (frm.doc.table_ttya || []).forEach((inv, idx) => {
            const packed_qty = packed_by_row[idx] || 0;
            if (packed_qty < inv.qty) {
                missing.push({ item: inv.item, item_name: inv.item_name || inv.item, need: inv.qty, packed: packed_qty });
            }
        });
    }

    return missing;
}
