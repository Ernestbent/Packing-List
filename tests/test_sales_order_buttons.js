// Run with: node tests/test_sales_order_buttons.js
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const source = fs.readFileSync(path.join(__dirname, '../autozonepro/public/js/hide_sales_order_butttons.js'), 'utf8');

function setup(state = 'Picking') {
    let handlers;
    const requests = [], changes = [], mapped = [];
    const context = {
        __: value => value,
        setTimeout() { throw new Error('Button refresh must not depend on a timer'); },
        frappe: {
            ui: {form: {on: (doctype, events) => { handlers = events; }}},
            call: request => { requests.push(request); },
            model: {open_mapped_doc: args => mapped.push(args)},
        },
    };
    vm.createContext(context);
    vm.runInContext(source, context);
    const frm = {
        doc: {name: 'SO-1', docstatus: 1, workflow_state: state},
        custom_buttons: {},
        cscript: {},
        add_custom_button(label, action, group) {
            changes.push({kind: 'add', label, group});
            const button = {label, action, group};
            this.custom_buttons[label] = button;
            return button;
        },
        remove_custom_button(label, group) {
            changes.push({kind: 'remove', label, group});
            delete this.custom_buttons[label];
        },
    };
    frm.cscript.refresh = function () {
        assert.equal(this, frm.cscript);
        frm.custom_buttons = {};
        frm.add_custom_button('Pick List', () => mapped.push('standard'), 'Create');
    };
    handlers.setup(frm);
    const refresh = () => { handlers.refresh(frm); return frm.cscript.refresh(); };
    const pickRequests = () => requests.filter(request => request.args.doctype === 'Pick List');
    return {frm, handlers, refresh, requests, changes, mapped, pickRequests};
}

test('eligible Pick List button stays in place during and after the existence check', () => {
    const {frm, refresh, changes, pickRequests, mapped} = setup();
    refresh();
    const button = frm.custom_buttons['Pick List'];
    pickRequests()[0].callback({message: []});
    assert.equal(frm.custom_buttons['Pick List'], button);
    assert.equal(changes.filter(change => change.label === 'Pick List' && change.kind === 'remove').length, 0);
    assert.equal(changes.filter(change => change.label === 'Pick List' && change.kind === 'add').length, 1);
    button.action();
    assert.deepEqual(mapped, ['standard']);
});

test('ineligible button is removed immediately after the standard toolbar is built', () => {
    const {frm, refresh, pickRequests} = setup('Approved');
    refresh();
    assert.equal(frm.custom_buttons['Pick List'], undefined);
    pickRequests()[0].callback({message: []});
    assert.equal(frm.custom_buttons['Pick List'], undefined);
});

test('existing Pick List hides creation button', () => {
    const {frm, refresh, pickRequests} = setup();
    refresh();
    pickRequests()[0].callback({message: [{name: 'PICK-1'}]});
    assert.equal(frm.custom_buttons['Pick List'], undefined);
});

test('old response cannot re-add button after newer refresh finds an existing list', () => {
    const {frm, refresh, pickRequests} = setup();
    refresh();
    const old = pickRequests()[0];
    refresh();
    pickRequests()[1].callback({message: [{name: 'PICK-1'}]});
    old.callback({message: []});
    assert.equal(frm.custom_buttons['Pick List'], undefined);
});

test('response for a different order cannot hide the current order button', () => {
    const {frm, refresh, pickRequests} = setup();
    refresh();
    const old = pickRequests()[0];
    frm.doc = {...frm.doc, name: 'SO-2'};
    refresh();
    const button = frm.custom_buttons['Pick List'];
    old.callback({message: [{name: 'OTHER-ORDER-PICK'}]});
    assert.equal(frm.custom_buttons['Pick List'], button);
    assert.equal(pickRequests()[1].args.filters[0][3], 'SO-2');
});

test('draft/cancelled orders cannot be modified by an earlier callback', () => {
    const {frm, refresh, pickRequests, changes} = setup();
    refresh();
    const old = pickRequests()[0];
    frm.doc.docstatus = 2;
    const changeCount = changes.length;
    old.callback({message: [{name: 'PICK-1'}]});
    assert.equal(changes.length, changeCount);
});

test('setup is idempotent and does not multiply refresh handlers or queries', () => {
    const {frm, handlers, refresh, requests} = setup();
    handlers.setup(frm);
    handlers.setup(frm);
    refresh();
    assert.equal(requests.length, 4);
});

test('custom creation still works when the standard controller did not add a button', () => {
    const {frm, refresh, pickRequests, mapped} = setup();
    refresh();
    delete frm.custom_buttons['Pick List'];
    pickRequests()[0].callback({message: []});
    frm.custom_buttons['Pick List'].action();
    assert.equal(mapped[0].method, 'erpnext.selling.doctype.sales_order.sales_order.create_pick_list');
    assert.equal(mapped[0].frm, frm);
});
