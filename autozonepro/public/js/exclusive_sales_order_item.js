const EXCLUSIVE_SALES_ORDER_ITEM = "CE300176PR";
const EXCLUSIVE_SALES_ORDER_WAREHOUSE = "SHAMBA LOC - APL";

frappe.ui.form.on("Sales Order", {
    async validate(frm) {
        const items = (frm.doc.items || []).filter((row) => row.item_code);
        if (
            items.length === 1 &&
            items[0].item_code === EXCLUSIVE_SALES_ORDER_ITEM
        ) {
            await set_exclusive_item_warehouse(frm, items[0].doctype, items[0].name);
        }
    },
});

frappe.ui.form.on("Sales Order Item", {
    items_add(frm, cdt, cdn) {
        const exclusive_item_exists = (frm.doc.items || []).some(
            (row) => row.name !== cdn && row.item_code === EXCLUSIVE_SALES_ORDER_ITEM
        );

        if (exclusive_item_exists) {
            remove_invalid_item_row(frm, cdt, cdn);
        }
    },

    async item_code(frm, cdt, cdn) {
        const row = locals[cdt][cdn];
        if (!row || row.item_code !== EXCLUSIVE_SALES_ORDER_ITEM) return;

        const another_item_exists = (frm.doc.items || []).some(
            (item) => item.name !== cdn && Boolean(item.item_code)
        );

        if (another_item_exists) {
            remove_invalid_item_row(frm, cdt, cdn);
            return;
        }

        await set_exclusive_item_warehouse(frm, cdt, cdn);
    },
});

async function set_exclusive_item_warehouse(frm, cdt, cdn) {
    const row = locals[cdt][cdn];
    if (!row || row.item_code !== EXCLUSIVE_SALES_ORDER_ITEM) return;

    if (frm.doc.set_warehouse !== EXCLUSIVE_SALES_ORDER_WAREHOUSE) {
        await frm.set_value("set_warehouse", EXCLUSIVE_SALES_ORDER_WAREHOUSE);
    }

    if (row.warehouse !== EXCLUSIVE_SALES_ORDER_WAREHOUSE) {
        await frappe.model.set_value(
            cdt,
            cdn,
            "warehouse",
            EXCLUSIVE_SALES_ORDER_WAREHOUSE
        );
    }
}

function remove_invalid_item_row(frm, cdt, cdn) {
    frappe.model.clear_doc(cdt, cdn);
    frm.refresh_field("items");
    frappe.throw({
        title: __("Item Must Be Ordered Separately"),
        message: __(
            "Item {0} must be ordered alone on its own Sales Order. Remove all other item rows or create a separate Sales Order for this item.",
            [EXCLUSIVE_SALES_ORDER_ITEM]
        ),
    });
}
