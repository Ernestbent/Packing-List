frappe.ui.form.on("Pick List", {
	refresh(frm) {
		if (frm.doc.docstatus === 0) {
			load_pick_list_pricing_context(frm).catch(() => {});
		}
	},
});

frappe.ui.form.on("Pick List Item", {
	before_locations_remove(frm, cdt, cdn) {
		return prepare_free_item_removal(frm, cdt, cdn);
	},

	locations_remove(frm, cdt, cdn) {
		remove_linked_free_items(frm, cdn);
	},
});

function get_pick_list_sales_order_items(frm) {
	return [...new Set((frm.doc.locations || []).map((row) => row.sales_order_item).filter(Boolean))];
}

async function load_pick_list_pricing_context(frm) {
	const sales_order_items = get_pick_list_sales_order_items(frm);
	if (!sales_order_items.length) {
		frm._pick_list_pricing_context = new Map();
		return frm._pick_list_pricing_context;
	}

	if (
		frm._pick_list_pricing_context &&
		sales_order_items.every((name) => frm._pick_list_pricing_context.has(name))
	) {
		return frm._pick_list_pricing_context;
	}

	const response = await frappe.call({
		method:
			"autozonepro.autozonepro.custom_scripts.pick_list_free_items.get_sales_order_item_pricing_context",
		args: { sales_order_items },
	});
	frm._pick_list_pricing_context = new Map(
		(response.message || []).map((row) => [row.name, row])
	);
	return frm._pick_list_pricing_context;
}

async function prepare_free_item_removal(frm, cdt, cdn) {
	if (frm.doc.docstatus !== 0) {
		return;
	}

	const removed_row = locals[cdt]?.[cdn];
	if (!removed_row?.sales_order_item) {
		return;
	}

	const context = await load_pick_list_pricing_context(frm);
	frm._pending_pick_list_removals ||= new Map();
	frm._pending_pick_list_removals.set(cdn, {
		context,
		sales_order_item: removed_row.sales_order_item,
	});
}

function remove_linked_free_items(frm, removed_row_name) {
	const pending_removal = frm._pending_pick_list_removals?.get(removed_row_name);
	frm._pending_pick_list_removals?.delete(removed_row_name);

	if (!pending_removal) {
		return;
	}

	const { context, sales_order_item } = pending_removal;
	const removed_item = context.get(sales_order_item);
	if (!removed_item || removed_item.is_free_item || !removed_item.pricing_rules.length) {
		return;
	}

	const remaining_rows = frm.doc.locations || [];
	const qualifying_rules = new Set();

	for (const row of remaining_rows) {
		const item = context.get(row.sales_order_item);
		if (!item || item.is_free_item) {
			continue;
		}

		for (const rule of item.pricing_rules) {
			qualifying_rules.add(`${item.sales_order}\u0000${rule}`);
		}
	}

	const free_rows = remaining_rows.filter((row) => {
		const item = context.get(row.sales_order_item);
		return (
			item?.is_free_item &&
			item.pricing_rules.length &&
			!item.pricing_rules.some((rule) =>
				qualifying_rules.has(`${item.sales_order}\u0000${rule}`)
			)
		);
	});

	for (const row of free_rows) {
		frappe.model.clear_doc(row.doctype, row.name);
	}

	if (free_rows.length) {
		frappe.show_alert(
			__n(
				"Removed {0} linked free item.",
				"Removed {0} linked free items.",
				free_rows.length,
				[free_rows.length]
			),
			5
		);
	}
}

if (
	typeof cur_frm !== "undefined" &&
	cur_frm?.doctype === "Pick List" &&
	cur_frm.doc.docstatus === 0
) {
	load_pick_list_pricing_context(cur_frm).catch(() => {});
}
