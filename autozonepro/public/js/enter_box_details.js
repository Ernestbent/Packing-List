frappe.ui.form.on('Packing List', {
    refresh(frm) {
        show_pack_button(frm);
        update_totals(frm);
    },

    custom_pick_list(frm) {
        if (frm.doc.custom_pick_list) {
            load_pl_items(frm);
        } else {
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
                title: __("Cannot Save – Items Missing"),
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

// --- Helper Functions ---

function show_pack_button(frm) {
    frm.remove_custom_button(__('Pack Items'));
    
    const should_show = frm.doc.custom_pick_list && 
                       frm.doc.docstatus === 0 && 
                       frm.doc.table_ttya && 
                       frm.doc.table_ttya.length > 0;
    
    if (should_show) {
        frm.add_custom_button(__('Pack Items'), function() {
            open_pack_dialog(frm);
        });
    }
}

function load_pl_items(frm) {
    if (!frm.doc.custom_pick_list) return;
    
    frappe.db.get_doc('Pick List', frm.doc.custom_pick_list)
    .then(function(pl) {
        if (!pl.locations || !pl.locations.length) {
            frappe.msgprint(__('No items found in this Pick List. Please click "Get Item Locations" on the Pick List first.'));
            return;
        }

        frm.clear_table('table_ttya');

        pl.locations.forEach(function(loc) {
            const row = frm.add_child('table_ttya');
            row.item = loc.item_code;
            row.item_name = loc.item_name;
            row.qty = loc.qty;
            row.uom = loc.uom;
        });

        frm.refresh_field('table_ttya');

        if (pl.customer) {
            frm.set_value('custom_customer', pl.customer);
        }

        if (pl.locations[0] && pl.locations[0].sales_order) {
            frm.set_value('custom_sales_order', pl.locations[0].sales_order);
        }

        show_pack_button(frm);
        update_totals(frm);
    });
}

function open_pack_dialog(frm) {
    const next_box = get_next_box_number(frm);
    
    const d = new frappe.ui.Dialog({
        title: __('Pack Items into Boxes'),
        size: 'large',
        fields: [
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
            const selected = get_selected_items(d);
            if (save_box(frm, values.box_number, values.box_weight, selected)) {
                frm.save()
                .then(() => {
                    
                    setTimeout(() => {
                        if (d && d.$wrapper && d.$wrapper.is(':visible')) {
                            const next_box = values.box_number + 1;
                            
                            const searchInput = d.fields_dict.search_container.$wrapper.find('#item-search-input');
                            if (searchInput.length) {
                                searchInput.val('');
                            }
                            
                            clear_all_selections(d);
                            
                            d.set_value('box_number', next_box);
                            d.set_value('box_weight', 0);
                            
                            render_items_with_checkboxes(frm, d);
                            
                            d.$wrapper.css('z-index', '1060');
                            d.show();
                            
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

    // Override the hide method to prevent accidental closing
    const originalHide = d.hide;
    d.hide = function(force) {
        if (force === true) {
            originalHide.call(d);
        } else {
            console.log('Prevented dialog close - use Save & Close to exit');
        }
    };

    d.fields_dict.box_number.df.onchange = () => {
        const box_number = d.get_value('box_number');
        load_box_data(frm, d, box_number);
    };

    render_search_box(frm, d);
    render_items_with_checkboxes(frm, d);
    d.show();
}

function load_box_data(frm, dialog, box_number) {
    const existing_items = (frm.doc.table_hqkk || []).filter(r => r.box_number === box_number);
    
    if (existing_items.length > 0) {
        const box_summary = (frm.doc.custom_box_summary || []).find(b => b.box_number === box_number);
        if (box_summary) {
            dialog.set_value('box_weight', box_summary.weight_kg || 0);
        }
        
        setTimeout(() => {
            render_items_with_checkboxes(frm, dialog);
            
            existing_items.forEach(box_item => {
                let row_idx = null;
                
                if (box_item.source_row_idx !== undefined && box_item.source_row_idx !== null) {
                    row_idx = box_item.source_row_idx;
                } else {
                    let item_occurrence = 0;
                    for (let i = 0; i < frm.doc.table_hqkk.length; i++) {
                        if (frm.doc.table_hqkk[i].item === box_item.item && frm.doc.table_hqkk[i].box_number === box_number) {
                            if (frm.doc.table_hqkk[i].name === box_item.name) {
                                break;
                            }
                            item_occurrence++;
                        }
                    }
                    
                    let occurrence_count = 0;
                    for (let i = 0; i < frm.doc.table_ttya.length; i++) {
                        if (frm.doc.table_ttya[i].item === box_item.item) {
                            if (occurrence_count === item_occurrence) {
                                row_idx = i;
                                break;
                            }
                            occurrence_count++;
                        }
                    }
                }
                
                if (row_idx !== null && row_idx !== undefined) {
                    const checkbox = dialog.fields_dict.items_html.$wrapper.find(`.item-checkbox[data-row-idx="${row_idx}"]`);
                    if (checkbox.length) {
                        checkbox.prop('checked', true);
                        const qtyInput = checkbox.closest('.pack-item-row').find('.qty-input');
                        qtyInput.show();
                        qtyInput.prop('disabled', false);
                        qtyInput.val(box_item.quantity);
                    }
                }
            });
        }, 100);
    } else {
        dialog.set_value('box_weight', 0);
        clear_all_selections(dialog);
        render_items_with_checkboxes(frm, dialog);
    }
}

function render_search_box(frm, dialog) {
    let html = `
        <style>
            .search-wrapper { position: relative; margin-bottom: 15px; }
            .search-input { width: 100%; padding: 10px 40px 10px 15px; border: 1px solid #d1d8dd; border-radius: 4px; font-size: 14px; }
            .search-input:focus { border-color: #2490ef; outline: none; box-shadow: 0 0 0 2px rgba(36,144,239,0.1); }
            .search-icon { position: absolute; right: 12px; top: 50%; transform: translateY(-50%); color: #888; pointer-events: none; }
        </style>
        <div class="search-wrapper">
            <input type="text" id="item-search-input" class="search-input" placeholder="Search items by name or code..." autocomplete="off">
            <svg class="search-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="11" cy="11" r="8"></circle>
                <path d="m21 21-4.35-4.35"></path>
            </svg>
        </div>
    `;
    
    dialog.fields_dict.search_container.$wrapper.html(html);
    
    const searchInput = dialog.fields_dict.search_container.$wrapper.find('#item-search-input');
    searchInput.on('input', function() {
        filter_items_list(dialog, $(this).val());
    });
}

function filter_items_list(dialog, search_term) {
    const itemsContainer = dialog.fields_dict.items_html.$wrapper.find('.items-container');
    const rows = itemsContainer.find('.pack-item-row');
    const noResultsMsg = itemsContainer.find('.no-results-filter');
    
    noResultsMsg.remove();
    
    if (!search_term || search_term.trim() === '') {
        rows.show();
        return;
    }
    
    const term = search_term.toLowerCase().trim();
    let visibleCount = 0;
    
    rows.each(function() {
        const row = $(this);
        const itemCode = (row.data('item-code') || '').toString().toLowerCase();
        const itemName = (row.data('item-name') || '').toString().toLowerCase();
        
        if (itemCode.includes(term) || itemName.includes(term)) {
            row.show();
            visibleCount++;
        } else {
            row.hide();
        }
    });
    
    if (visibleCount === 0) {
        itemsContainer.append(`<div class="no-results-filter" style="text-align: center; padding: 40px; color: #888;">No items match your search</div>`);
    }
}

function render_items_with_checkboxes(frm, dialog) {
    const items = frm.doc.table_ttya || [];
    const current_box = dialog.get_value('box_number');
    
    const has_source_row_idx = frm.doc.table_hqkk && frm.doc.table_hqkk.some(r => r.source_row_idx !== undefined && r.source_row_idx !== null);
    
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
            // Calculate total packed quantity for this item/row across ALL boxes
            let total_packed = 0;
            
            if (!has_source_row_idx) {
                (frm.doc.table_hqkk || []).forEach(box_item => {
                    if (box_item.item === item.item) {
                        total_packed += (box_item.quantity || 0);
                    }
                });
            } else {
                (frm.doc.table_hqkk || []).forEach(box_item => {
                    if (box_item.source_row_idx === idx) {
                        total_packed += (box_item.quantity || 0);
                    }
                });
            }
            
            const remaining = Math.max(0, item.qty - total_packed);
            
            // Add back the quantity from current box for display purposes
            let display_remaining = remaining;
            if (!has_source_row_idx) {
                (frm.doc.table_hqkk || []).forEach(box_item => {
                    if (box_item.box_number === current_box && box_item.item === item.item) {
                        display_remaining += (box_item.quantity || 0);
                    }
                });
            } else {
                (frm.doc.table_hqkk || []).forEach(box_item => {
                    if (box_item.box_number === current_box && box_item.source_row_idx === idx) {
                        display_remaining += (box_item.quantity || 0);
                    }
                });
            }

            // Check if this item exists in the current box being edited
            const is_in_current_box = (frm.doc.table_hqkk || []).some(box_item => 
                box_item.box_number === current_box && box_item.source_row_idx === idx
            );

            // For display, show the quantity packed in this box if editing
            let display_available;
            if (is_in_current_box) {
                const saved_qty = (frm.doc.table_hqkk || []).find(
                    box_item => box_item.box_number === current_box && box_item.source_row_idx === idx
                )?.quantity || 0;
                display_available = saved_qty;
            } else {
                display_available = display_remaining;
            }

            // --- KEY FIX ---
            // Only grey out items that are fully packed in OTHER boxes (not the current box)
            let packed_in_other_boxes = 0;
            if (!has_source_row_idx) {
                (frm.doc.table_hqkk || []).forEach(box_item => {
                    if (box_item.box_number !== current_box && box_item.item === item.item) {
                        packed_in_other_boxes += (box_item.quantity || 0);
                    }
                });
            } else {
                (frm.doc.table_hqkk || []).forEach(box_item => {
                    if (box_item.box_number !== current_box && box_item.source_row_idx === idx) {
                        packed_in_other_boxes += (box_item.quantity || 0);
                    }
                });
            }
            const is_fully_packed_elsewhere = packed_in_other_boxes >= item.qty;

            let disabled = false;
            let row_class = 'pack-item-row';
            let remaining_class = 'item-remaining';
            let status_text;

            if (is_in_current_box) {
                // Item is in this box — always editable, never greyed
                disabled = false;
                row_class = 'pack-item-row';
                remaining_class = 'item-remaining';
                status_text = `Editing: Packed <strong>${display_available}</strong> in this box`;
            } else if (is_fully_packed_elsewhere) {
                // Fully packed in OTHER boxes — grey it out
                disabled = 'disabled';
                row_class = 'pack-item-row fully-packed';
                remaining_class = 'item-remaining zero';
                status_text = '✓ Fully Packed';
            } else {
                // Available to pack
                disabled = '';
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
                    <input type="checkbox" class="item-checkbox" data-row-idx="${idx}" data-max="${display_available}" ${disabled ? 'disabled' : ''}
                           onclick="event.stopPropagation()" onchange="window.toggleQtyInput(this)">
                    <div class="item-details">
                        <div class="item-name">${item.item_name || item.item}</div>
                        <div class="item-code">${item.item}</div>
                        <div class="${remaining_class}">
                            ${status_text}
                        </div>
                    </div>
                    <input type="number" class="qty-input" data-row-idx="${idx}" placeholder="Qty"
                           min="1" max="${display_available}" step="1" disabled onclick="event.stopPropagation()" style="display: none;">
                </div>
            `;
        });
    }

    html += `</div>`;
    dialog.fields_dict.items_html.$wrapper.html(html);

    // Auto-check and show quantity inputs for items in the current box
    setTimeout(() => {
        const currentBoxItems = (frm.doc.table_hqkk || []).filter(r => r.box_number === current_box);
        currentBoxItems.forEach(boxItem => {
            const checkbox = dialog.fields_dict.items_html.$wrapper.find(`.item-checkbox[data-row-idx="${boxItem.source_row_idx}"]`);
            if (checkbox.length) {
                checkbox.prop('checked', true);
                const qtyInput = checkbox.closest('.pack-item-row').find('.qty-input');
                qtyInput.show();
                qtyInput.prop('disabled', false);
                qtyInput.val(boxItem.quantity);
            }
        });
    }, 100);

    window.toggleQtyInput = function(checkbox) {
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
    
    window.toggleCheckboxOnRow = function(row) {
        const checkbox = row.querySelector('.item-checkbox');
        if (!checkbox.disabled) {
            checkbox.checked = !checkbox.checked;
            window.toggleQtyInput(checkbox);
        }
    };
}

function clear_all_selections(dialog) {
    const wrapper = dialog.fields_dict.items_html.$wrapper;
    wrapper.find('.item-checkbox:checked').each(function() {
        $(this).prop('checked', false);
        const qtyInput = $(this).closest('.pack-item-row').find('.qty-input');
        qtyInput.hide();
        qtyInput.prop('disabled', true);
        qtyInput.val('');
    });
}

function get_selected_items(dialog) {
    const selected = [];
    const wrapper = dialog.fields_dict.items_html.$wrapper;
    
    wrapper.find('.item-checkbox:checked').each(function() {
        const checkbox = $(this);
        const rowIdx = checkbox.data('row-idx');
        const qtyInput = wrapper.find(`.qty-input[data-row-idx="${rowIdx}"]`);
        const qty = parseFloat(qtyInput.val()) || 0;
        
        if (qty > 0) {
            selected.push({ row_idx: rowIdx, quantity: qty });
        }
    });
    
    return selected;
}

function save_box(frm, box_number, weight, items) {
    if (!weight || weight <= 0) {
        frappe.msgprint({ title: __('Invalid Weight'), message: __('Please enter a valid box weight.'), indicator: 'red' });
        return false;
    }

    if (!items.length) {
        frappe.msgprint({ title: __('No Items Selected'), message: __('Please select at least one item to pack.'), indicator: 'red' });
        return false;
    }

    const has_source_row_idx = frm.doc.table_hqkk && frm.doc.table_hqkk.some(r => r.source_row_idx !== undefined && r.source_row_idx !== null);

    // Validate quantities
    for (const item of items) {
        const row = frm.doc.table_ttya[item.row_idx];
        if (!row) continue;
        
        let packed_in_other_boxes = 0;
        
        if (!has_source_row_idx) {
            (frm.doc.table_hqkk || []).forEach(box_item => {
                if (box_item.box_number !== box_number && box_item.item === row.item) {
                    packed_in_other_boxes += (box_item.quantity || 0);
                }
            });
        } else {
            (frm.doc.table_hqkk || []).forEach(box_item => {
                if (box_item.box_number !== box_number && box_item.source_row_idx === item.row_idx) {
                    packed_in_other_boxes += (box_item.quantity || 0);
                }
            });
        }
        
        const available = row.qty - packed_in_other_boxes;
        
        if (item.quantity > available) {
            frappe.msgprint({
                title: __('Quantity Exceeds Available'),
                message: __('Cannot pack {0} units of {1}. Only {2} available.', [item.quantity, row.item, available]),
                indicator: 'red'
            });
            return false;
        }
    }

    // Remove old items from this box (if editing an existing box)
    frm.doc.table_hqkk = (frm.doc.table_hqkk || []).filter(r => r.box_number !== box_number);

    // Add new items
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

    // Update or create box summary
    let summary = (frm.doc.custom_box_summary || []).find(b => b.box_number === box_number);
    if (!summary) {
        summary = frm.add_child('custom_box_summary');
        summary.box_number = box_number;
    }
    summary.weight_kg = weight;

    frm.refresh_field('table_hqkk');
    frm.refresh_field('custom_box_summary');
    update_totals(frm);
    
    return true;
}

function calculate_packed_qty_by_row(frm) {
    const packed = {};
    (frm.doc.table_hqkk || []).forEach(row => {
        let source_idx = row.source_row_idx;
        
        if (source_idx === undefined || source_idx === null) {
            const item_code = row.item;
            let occurrence = 0;
            
            for (let i = 0; i < frm.doc.table_hqkk.length; i++) {
                if (frm.doc.table_hqkk[i].item === item_code) {
                    if (i === frm.doc.table_hqkk.indexOf(row)) {
                        break;
                    }
                    occurrence++;
                }
            }
            
            let matched_count = 0;
            for (let i = 0; i < frm.doc.table_ttya.length; i++) {
                if (frm.doc.table_ttya[i].item === item_code) {
                    if (matched_count === occurrence) {
                        source_idx = i;
                        break;
                    }
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

function get_next_box_number(frm) {
    const used = (frm.doc.table_hqkk || []).map(r => r.box_number).filter(Boolean);
    return used.length ? Math.max(...used) + 1 : 1;
}

function update_totals(frm) {
    const box_numbers = new Set((frm.doc.table_hqkk || []).map(r => r.box_number).filter(Boolean));
    frm.set_value('total_boxes', box_numbers.size);
    frm.set_value('total_qty', (frm.doc.table_hqkk || []).reduce((sum, r) => sum + (r.quantity || 0), 0));
}

function get_missing_items(frm) {
    const missing = [];
    
    const has_source_row_idx = frm.doc.table_hqkk && frm.doc.table_hqkk.some(r => r.source_row_idx !== undefined && r.source_row_idx !== null);
    
    if (!has_source_row_idx && frm.doc.table_hqkk && frm.doc.table_hqkk.length > 0) {
        const packed_by_item = {};
        (frm.doc.table_hqkk || []).forEach(row => {
            packed_by_item[row.item] = (packed_by_item[row.item] || 0) + (row.quantity || 0);
        });
        
        (frm.doc.table_ttya || []).forEach((inv) => {
            const packed_qty = packed_by_item[inv.item] || 0;
            if (packed_qty < inv.qty) {
                missing.push({
                    item: inv.item,
                    item_name: inv.item_name || inv.item,
                    need: inv.qty,
                    packed: packed_qty
                });
            }
        });
    } else {
        const packed_by_row = calculate_packed_qty_by_row(frm);
        
        (frm.doc.table_ttya || []).forEach((inv, idx) => {
            const packed_qty = packed_by_row[idx] || 0;
            if (packed_qty < inv.qty) {
                missing.push({
                    item: inv.item,
                    item_name: inv.item_name || inv.item,
                    need: inv.qty,
                    packed: packed_qty
                });
            }
        });
    }
    
    return missing;
}