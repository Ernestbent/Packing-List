import frappe


def execute(filters=None):
	models = get_models(filters)
	columns = get_columns(models)
	data = get_data(filters)
	return columns, data


@frappe.whitelist()
def get_model_options(txt=""):
	return frappe.get_all(
		"Item",
		filters=[
			["Item", "disabled", "=", 0],
			["Item", "custom_model", "!=", ""],
			["Item", "custom_model", "like", f"%{txt}%"],
		],
		pluck="custom_model",
		distinct=True,
		order_by="custom_model",
		limit_page_length=50,
	)


def get_models(filters):
	filters = filters or {}
	conditions = "disabled = 0 and custom_model is not null and custom_model != ''"
	if filters.get("item_group"):
		conditions += " and item_group = %(item_group)s"
	if filters.get("model"):
		conditions += " and custom_model = %(model)s"

	rows = frappe.db.sql("""
		select distinct custom_model
		from `tabItem`
		where {conditions}
		order by custom_model
	""".format(conditions=conditions), filters, as_dict=1)

	return [row.custom_model for row in rows]


def get_columns(models):
	columns = [
		{"label": "Group", "fieldname": "group", "fieldtype": "Data", "width": 150},
		{"label": "Sub Group", "fieldname": "sub_group", "fieldtype": "Data", "width": 150},
		{"label": "Brand", "fieldname": "brand", "fieldtype": "Data", "width": 100},
	]
	for model in models:
		fieldname = frappe.scrub(model)
		columns.append({"label": model, "fieldname": fieldname, "fieldtype": "Currency", "width": 100})
	return columns


def get_data(filters):
	filters = filters or {}

	## walk the Item Group tree once, same as before, to resolve each item's top-level group
	group_rows = frappe.db.sql("select name, parent_item_group from `tabItem Group`", as_dict=1)
	parent_map = {}
	for row in group_rows:
		parent_map[row.name] = row.parent_item_group

	resolved = {}

	def resolve_group(item_group):
		if item_group in resolved:
			return resolved[item_group]
		path = [item_group]
		current = item_group
		while parent_map.get(current) and parent_map.get(current) != "All Item Groups":
			current = parent_map[current]
			path.append(current)
		top = path[-1]
		resolved[item_group] = top
		return top

	# Items without a model cannot populate a dynamic price column.
	conditions = "disabled = 0 and custom_model is not null and custom_model != ''"
	if filters.get("item_group"):
		conditions += " and item_group = %(item_group)s"
	if filters.get("model"):
		conditions += " and custom_model = %(model)s"

	items = frappe.db.sql("""
		select item_group, brand, custom_model, standard_rate
		from `tabItem`
		where {conditions}
		order by item_group, brand, custom_model
	""".format(conditions=conditions), filters, as_dict=1)

	# One row per brand; each corresponding model fills a price column on that row.
	rows = {}
	for item in items:
		top = resolve_group(item.item_group)
		if top == "Products":
			continue

		sub = "" if item.item_group == top else item.item_group
		key = (top, sub, item.brand)

		if key not in rows:
			rows[key] = {"group": top, "sub_group": sub, "brand": item.brand}

		fieldname = frappe.scrub(item.custom_model)
		rows[key][fieldname] = item.standard_rate

	# Sort by the resolved first column before the child fields. This keeps every
	# subgroup/brand belonging to a Group together until that Group is exhausted.
	return sorted(
		rows.values(),
		key=lambda row: (
			(row.get("group") or "").casefold(),
			(row.get("sub_group") or "").casefold(),
			(row.get("brand") or "").casefold(),
		),
	)
