// Run with: node tests/test_packing_dialog.js
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const script = fs.readFileSync(path.join(__dirname, '../autozonepro/public/js/enter_box_details.js'), 'utf8');

function setup() {
    const messages = [], dialogs = [];
    class Wrapper {
        constructor() { this.value = ''; this.markup = ''; }
        html(value) { this.markup = value; return this; }
        find() { return this; }
        on() { return this; }
        remove() { return this; }
        show() { return this; }
        each() { return this; }
        prop(key, value) { this[key] = value; return this; }
        val(value) { if (value === undefined) return this.value; this.value = value; return this; }
    }
    class Dialog {
        constructor(options) {
            this.options = options;
            this.values = {};
            this.fields_dict = {};
            this.primary = new Wrapper();
            this.$wrapper = {is: () => this.visible};
            for (const field of options.fields) {
                this.values[field.fieldname] = field.default;
                this.fields_dict[field.fieldname] = {df: field, $wrapper: new Wrapper()};
            }
            dialogs.push(this);
        }
        get_value(key) { return this.values[key]; }
        set_value(key, value) {
            const changed = this.values[key] !== value;
            this.values[key] = value;
            if (changed && this.fields_dict[key].df.onchange) this.fields_dict[key].df.onchange();
            return Promise.resolve();
        }
        get_primary_btn() { return this.primary; }
        show() { this.visible = true; }
        hide() { this.visible = false; }
    }
    const context = {
        frappe: {ui: {form: {on() {}}, Dialog}, msgprint: msg => messages.push(msg), db: {},
            utils: {escape_html: value => String(value).replaceAll('&', '&amp;').replaceAll('"', '&quot;').replaceAll('<', '&lt;')}},
        __: value => value, window: {}, setTimeout,
    };
    vm.createContext(context);
    vm.runInContext(script, context);
    return {context, messages, dialogs};
}

const item = (qty, code = 'A', uom = 'Nos') => ({item: code, item_name: code, qty, uom});
const packed = (quantity, box_number = 1, code = 'A', extra = {}) => ({item: code, quantity, box_number, uom: 'Nos', ...extra});
const selected = (quantity, code = 'A', uom = 'Nos') => ({item: code, quantity, uom});
function form(items, boxes = []) {
    return {
        doc: {custom_pick_list: 'PICK-1', docstatus: 0, table_ttya: items, table_hqkk: boxes, custom_box_summary: []},
        add_child(table) { const row = {}; this.doc[table].push(row); return row; },
        clear_table(table) { this.doc[table] = []; },
        set_value(key, value) {
            if (typeof key === 'object') Object.assign(this.doc, key);
            else this.doc[key] = value;
            return Promise.resolve();
        },
        refresh_fields() {}, refresh_field() {}, remove_custom_button() {}, add_custom_button() {},
        dirty() { this.unsaved = true; }, is_dirty() { return !!this.unsaved; },
        async save() { this.unsaved = false; },
    };
}

test('duplicate item lines require their combined quantity, including after reload', () => {
    const {context: c} = setup();
    const frm = form([item(5), item(5)], [packed(5)]);
    assert.equal(c.get_missing_items(frm)[0].need, 10);
    assert(c.save_box(frm, 2, 1, '3 PLY', [selected(5)]));
    frm.doc = JSON.parse(JSON.stringify(frm.doc));
    assert.equal(c.get_missing_items(frm).length, 0);
    assert.equal(frm.doc.total_qty, 10);
});

test('mixed legacy and indexed rows cannot overpack', () => {
    const {context: c} = setup();
    const frm = form([item(10)], [packed(4), packed(6, 2, 'A', {source_row_idx: 0})]);
    assert.equal(c.save_box(frm, 3, 1, '3 PLY', [selected(4)]), false);
    assert.equal(frm.doc.table_hqkk.length, 2);
});

test('item identity is independent of row order and transient source index', () => {
    const {context: c} = setup();
    const frm = form([item(3, 'B'), item(5)], [packed(5, 1, 'A', {source_row_idx: 0})]);
    assert.equal(c.get_missing_items(frm).length, 1);
    assert.equal(c.get_missing_items(frm)[0].item, 'B');
    assert.equal(c.save_box(frm, 2, 1, '3 PLY', [selected(1)]), false);
});

test('units of measure stay separate and unexpected items are incomplete', () => {
    const {context: c} = setup();
    const frm = form([item(5), item(2, 'A', 'Box')], [packed(5)]);
    assert.equal(c.get_missing_items(frm)[0].need, 2);
    assert(c.save_box(frm, 2, 1, '3 PLY', [selected(2, 'A', 'Box')]));
    frm.doc.table_hqkk.push(packed(1, 3, 'UNEXPECTED'));
    assert.equal(c.get_missing_items(frm)[0].item, 'UNEXPECTED');
});

test('editing a saved box restores selection and uses all remaining capacity', () => {
    const {context: c, dialogs} = setup();
    const frm = form([item(10)], [packed(3), packed(2, 2)]);
    frm.doc.custom_box_summary.push({box_number: 1, weight_kg: 4, box_type: '5 PLY'});
    c.open_pack_dialog(frm);
    const d = dialogs[0];
    d.set_value('box_number', 1);
    const html = d.fields_dict.items_html.$wrapper.markup;
    assert.match(html, /min="1" max="8"/);
    assert.match(html, /value="3"/);
    assert.match(html, /checked/);
    assert.equal(d.get_value('box_weight'), 4);
    assert.equal(d.get_value('box_type'), '5 PLY');
    assert(c.save_box(frm, 1, 4, '5 PLY', [selected(8)]));
    assert.equal(frm.doc.total_qty, 10);
    assert.equal(frm.doc.table_hqkk.length, 2);
});

test('invalid quantities and box numbers leave existing box intact', () => {
    const {context: c} = setup();
    const frm = form([item(10)], [packed(3)]);
    for (const qty of [0, -1, 1.5, NaN, Infinity, 11]) {
        assert.equal(c.save_box(frm, 1, 1, '3 PLY', [selected(qty)]), false);
    }
    for (const number of [0, -1, 1.5]) {
        assert.equal(c.save_box(frm, number, 1, '3 PLY', [selected(3)]), false);
    }
    assert.equal(frm.doc.table_hqkk[0].quantity, 3);
});

test('changing Pick List clears packing, summaries and stale linked fields', async () => {
    const {context: c} = setup();
    const frm = form([item(10)], [packed(10)]);
    frm.doc.custom_box_summary.push({box_number: 1});
    frm.doc.custom_sales_order = 'OLD';
    c.frappe.db.get_doc = async () => ({locations: [{item_code: 'B', qty: 6, uom: 'Nos'}]});
    await c.load_pl_items(frm);
    assert.equal(frm.doc.table_hqkk.length, 0);
    assert.equal(frm.doc.custom_box_summary.length, 0);
    assert.equal(frm.doc.custom_sales_order, '');
    assert.equal(frm.doc.table_ttya[0].item, 'B');
    assert.equal(c.get_missing_items(frm)[0].need, 6);
});

test('out-of-order Pick List responses cannot restore an old list', async () => {
    const {context: c} = setup();
    const frm = form([item(10)]);
    let finishOld;
    c.frappe.db.get_doc = (_, name) => name === 'PICK-1'
        ? new Promise(resolve => { finishOld = resolve; })
        : Promise.resolve({locations: [{item_code: 'B', qty: 6, uom: 'Nos'}]});
    const old = c.load_pl_items(frm);
    await new Promise(resolve => setImmediate(resolve));
    frm.doc.custom_pick_list = 'PICK-2';
    await c.load_pl_items(frm);
    finishOld({locations: [{item_code: 'A', qty: 10, uom: 'Nos'}]});
    await old;
    assert.equal(frm.doc.table_ttya[0].item, 'B');
});

test('saving the final box closes dialog without advancing; reopening edits existing box', async () => {
    const {context: c, dialogs, messages} = setup();
    const frm = form([item(5)]);
    c.get_selected_items = () => [selected(5)];
    c.open_pack_dialog(frm);
    const d = dialogs[0];
    await d.options.primary_action({box_number: 1, box_weight: 2, box_type: '3 PLY'});
    assert.equal(d.visible, false);
    assert.equal(d.get_value('box_number'), 1);
    assert.equal(messages.at(-1).title, 'All Items Packed!');
    c.open_pack_dialog(frm);
    assert.equal(dialogs[1].get_value('box_number'), 1);
});

test('partial packing advances to an unused box, preserving other existing boxes', async () => {
    const {context: c, dialogs} = setup();
    const frm = form([item(10)], [packed(2), packed(2, 5)]);
    c.get_selected_items = () => [selected(3)];
    c.open_pack_dialog(frm);
    const d = dialogs[0];
    await d.set_value('box_number', 1);
    await d.options.primary_action({box_number: 1, box_weight: 2, box_type: '3 PLY'});
    assert.equal(d.visible, true);
    assert.equal(d.get_value('box_number'), 6);
    assert.equal(frm.doc.table_hqkk.find(row => row.box_number === 5).quantity, 2);
});

test('failed save keeps dialog on current box and allows retry', async () => {
    const {context: c, dialogs, messages} = setup();
    const frm = form([item(5)]);
    frm.save = async () => { throw new Error('save rejected'); };
    c.get_selected_items = () => [selected(5)];
    c.open_pack_dialog(frm);
    const d = dialogs[0];
    const values = {box_number: 1, box_weight: 2, box_type: '3 PLY'};
    await d.options.primary_action(values);
    assert.equal(d.visible, true);
    assert.equal(d.get_value('box_number'), 1);
    assert.equal(d.primary.disabled, false);
    assert(!messages.some(msg => msg.title === 'All Items Packed!'));
    frm.save = async () => { frm.unsaved = false; };
    await d.options.primary_action(values);
    assert.equal(d.visible, false);
    assert.equal(frm.doc.table_hqkk.length, 1);
});

test('a failed save whose promise resolves still cannot announce completion', async () => {
    const {context: c, dialogs, messages} = setup();
    const frm = form([item(5)]);
    // Frappe catches save errors internally and may resolve while the form stays dirty.
    frm.save = async () => {};
    c.get_selected_items = () => [selected(5)];
    c.open_pack_dialog(frm);
    const d = dialogs[0];
    await d.options.primary_action({box_number: 1, box_weight: 2, box_type: '3 PLY'});
    assert.equal(d.visible, true);
    assert.equal(d.get_value('box_number'), 1);
    assert.equal(d.primary.disabled, false);
    assert(!messages.some(msg => msg.title === 'All Items Packed!'));
});

test('repeated Save clicks do not start overlapping saves', async () => {
    const {context: c, dialogs} = setup();
    const frm = form([item(5)]);
    let finishSave, saves = 0;
    frm.save = () => { saves++; return new Promise(resolve => { finishSave = resolve; }); };
    c.get_selected_items = () => [selected(5)];
    c.open_pack_dialog(frm);
    const d = dialogs[0];
    const values = {box_number: 1, box_weight: 2, box_type: '3 PLY'};
    const saving = d.options.primary_action(values);
    await d.options.primary_action(values);
    assert.equal(saves, 1);
    assert.equal(d.visible, true);
    frm.unsaved = false;
    finishSave();
    await saving;
    assert.equal(d.visible, false);
});

test('checkbox extraction retains invalid selected quantities for validation', () => {
    const {context: c} = setup();
    c.$ = element => element;
    const checkbox = {data: () => 0};
    const d = {
        _packing_items: [item(5)],
        fields_dict: {items_html: {$wrapper: {find: selector => selector === '.item-checkbox:checked'
            ? {each: callback => callback.call(checkbox)}
            : {val: () => ''}}}},
    };
    const items = c.get_selected_items(d);
    assert.equal(items.length, 1);
    assert.equal(items[0].item, 'A');
    assert.equal(items[0].quantity, 0);
    assert.equal(c.save_box(form([item(5)]), 1, 1, '3 PLY', items), false);
});

test('fully packed item is disabled in another box but editable in its own box', () => {
    const {context: c, dialogs} = setup();
    const frm = form([item(5), item(2, 'B')], [packed(5)]);
    c.open_pack_dialog(frm);
    const d = dialogs[0];
    assert.equal(d.get_value('box_number'), 2);
    let html = d.fields_dict.items_html.$wrapper.markup;
    assert.match(html, /class="pack-item-row fully-packed"/);
    assert.match(html, /data-row-idx="0" data-max="0"\s+disabled/);
    d.set_value('box_number', 1);
    html = d.fields_dict.items_html.$wrapper.markup;
    assert.match(html, /Fully Packed \(editing this box\)/);
    assert.match(html, /data-row-idx="0" data-max="5"\s+checked/);
});

test('historical overpacking never displays Fully Packed or passes completion', () => {
    const {context: c, dialogs} = setup();
    const frm = form([item(5)], [packed(6)]);
    c.open_pack_dialog(frm);
    const d = dialogs[0];
    for (const box of [2, 1]) {
        d.set_value('box_number', box);
        const html = d.fields_dict.items_html.$wrapper.markup;
        assert.match(html, /Overpacked:/);
        assert.doesNotMatch(html, /Fully Packed/);
        assert.equal(c.get_missing_items(frm).length, 1);
    }
});

test('reducing a completed box makes the item available to pack again', () => {
    const {context: c, dialogs} = setup();
    const frm = form([item(5)], [packed(5)]);
    assert(c.save_box(frm, 1, 1, '3 PLY', [selected(3)]));
    c.open_pack_dialog(frm);
    const d = dialogs[0];
    assert.equal(d.get_value('box_number'), 2);
    assert.match(d.fields_dict.items_html.$wrapper.markup, /Available for this box: <strong>2<\/strong>/);
    assert.doesNotMatch(d.fields_dict.items_html.$wrapper.markup, /Fully Packed/);
    assert.equal(c.get_missing_items(frm).length, 1);
});
