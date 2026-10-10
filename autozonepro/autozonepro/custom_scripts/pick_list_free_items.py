import json

import frappe
from frappe import _


def _get_pricing_rules(value):
	"""Return pricing-rule names from either ERPNext's JSON or CSV storage format."""
	if not value:
		return set()

	if isinstance(value, (list, tuple, set)):
		return {rule for rule in value if rule}

	value = value.strip()
	if value.startswith("["):
		try:
			return {rule for rule in json.loads(value) if rule}
		except (TypeError, ValueError):
			return set()

	return {rule.strip() for rule in value.split(",") if rule.strip()}


def _find_orphaned_free_item_references(item_rows):
	"""Find free Sales Order rows whose qualifying row is absent from a Pick List."""
	qualifying_rules = set()

	for row in item_rows:
		if not row.get("is_free_item"):
			qualifying_rules.update(
				(row.get("parent"), rule) for rule in _get_pricing_rules(row.get("pricing_rules"))
			)

	orphaned = set()
	for row in item_rows:
		if not row.get("is_free_item"):
			continue

		free_item_rules = _get_pricing_rules(row.get("pricing_rules"))
		if free_item_rules and not any(
			(row.get("parent"), rule) in qualifying_rules for rule in free_item_rules
		):
			orphaned.add(row.get("name"))

	return orphaned


@frappe.whitelist()
def get_sales_order_item_pricing_context(sales_order_items):
	"""Return the pricing-rule relationship needed for immediate Pick List updates."""
	if isinstance(sales_order_items, str):
		sales_order_items = frappe.parse_json(sales_order_items)

	sales_order_items = list({item for item in (sales_order_items or []) if item})
	if not sales_order_items:
		return []

	rows = frappe.get_all(
		"Sales Order Item",
		filters={"name": ("in", sales_order_items)},
		fields=["name", "parent", "is_free_item", "pricing_rules"],
	)
	return [
		{
			"name": row.name,
			"sales_order": row.parent,
			"is_free_item": row.is_free_item,
			"pricing_rules": sorted(_get_pricing_rules(row.pricing_rules)),
		}
		for row in rows
	]


@frappe.whitelist()
def get_orphaned_free_item_sales_order_items(sales_order_items):
	"""Return free Sales Order item references that no longer have a paid item in the Pick List."""
	context = get_sales_order_item_pricing_context(sales_order_items)
	item_rows = [
		frappe._dict(
			name=row["name"],
			parent=row["sales_order"],
			is_free_item=row["is_free_item"],
			pricing_rules=row["pricing_rules"],
		)
		for row in context
	]
	return sorted(_find_orphaned_free_item_references(item_rows))


def remove_orphaned_free_items(doc, method=None):
	"""Remove free Pick List rows after all matching qualifying rows have been removed."""
	references = [row.sales_order_item for row in doc.locations if row.sales_order_item]
	orphaned_references = set(get_orphaned_free_item_sales_order_items(references))
	if not orphaned_references:
		return

	removed = 0
	for row in list(doc.locations):
		if row.sales_order_item in orphaned_references:
			doc.remove(row)
			removed += 1

	if removed:
		frappe.msgprint(
			_("Removed {0} free item row(s) because their qualifying item is no longer in the Pick List.").format(
				removed
			),
			alert=True,
		)
