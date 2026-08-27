# Copyright (c) 2013, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt


import frappe
from frappe import _, scrub
from frappe.query_builder import DocType
from frappe.query_builder.functions import IfNull
from frappe.utils import add_days, add_to_date, flt, getdate, strip_html

from erpnext.accounts.utils import get_fiscal_year


def execute(filters=None):
	return Analytics(filters).run()


@frappe.whitelist()
def get_secondary_filter_options(filter_by, txt=""):
	search = f"%{txt}%"
	if filter_by == "Customer":
		customers = frappe.get_all(
			"Customer",
			filters={"name": ["like", search]},
			fields=["name", "customer_name"],
			order_by="name",
			limit_page_length=50,
		)
		return [
			{"value": d.name, "label": d.name, "description": d.customer_name}
			for d in customers
		]

	if filter_by in ["Region", "District", "Route"]:
		fieldname = filter_by.lower()
		return frappe.get_all(
			"Customer",
			filters=[["Customer", fieldname, "!=", ""], ["Customer", fieldname, "like", search]],
			pluck=fieldname,
			distinct=True,
			order_by=fieldname,
			limit_page_length=50,
		)

	if filter_by == "Sales Person":
		return frappe.get_all(
			"Sales Team",
			filters={
				"parenttype": "Customer",
				"sales_person": ["like", search],
			},
			pluck="sales_person",
			distinct=True,
			order_by="sales_person",
			limit_page_length=50,
		)
	if filter_by in ["Customer Group", "Item Group", "Item", "Project"]:
		doctype = filter_by
		return frappe.get_all(
			doctype,
			filters={"name": ["like", search]},
			pluck="name",
			order_by="name",
			limit_page_length=50,
		)

	if filter_by == "Order Type":
		return frappe.get_all(
			"Sales Order",
			filters={"docstatus": 1, "order_type": ["like", search]},
			pluck="order_type",
			distinct=True,
			order_by="order_type",
			limit_page_length=50,
		)

	return []


class Analytics:
	unique_item_tree_types = ["Customer", "Region", "District", "Sales Person", "Route", "Item"]
	stock_warehouses = [
		"Main Loc - APL",
		"Cont. No. 1 = MAEU-8382503 - APL",
		"Cont. No. 2 = FTBU-8875500 - APL",
	]

	def __init__(self, filters=None):
		self.filters = frappe._dict(filters or {})
		self.date_field = (
			"transaction_date"
			if self.filters.doc_type in ["Sales Order", "Purchase Order", "Sales Loss"]
			else "posting_date"
		)
		self.months = [
			"Jan",
			"Feb",
			"Mar",
			"Apr",
			"May",
			"Jun",
			"Jul",
			"Aug",
			"Sep",
			"Oct",
			"Nov",
			"Dec",
		]
		self.filtered_item_codes = self.get_filtered_item_codes()
		self.filtered_customer_names = self.get_filtered_customer_names()
		self.get_period_date_ranges()

	def get_secondary_filters(self):
		filters = []
		for index in range(1, 6):
			suffix = "" if index == 1 else f"_{index}"
			filter_by = self.filters.get(f"secondary_filter_by{suffix}")
			filter_value = self.filters.get(f"secondary_filter_value{suffix}")
			if filter_by and filter_value:
				filters.append((filter_by, filter_value))
		return filters

	def get_filtered_item_codes(self):
		item_classification = self.filters.get("item_classification") or "All"
		item_filters = {}
		if self.filters.tree_type == "Item" and item_classification not in ["All", "All Items"]:
			fieldname = (
				"custom_slow_moving"
				if item_classification == "Slow Moving Items"
				else "custom_focus_item"
			)
			item_filters[fieldname] = 1

		for filter_by, filter_value in self.get_secondary_filters():
			if filter_by == "Item":
				item_filters["name"] = filter_value
			elif filter_by == "Item Group":
				item_filters["item_group"] = filter_value

		if not item_filters:
			return None
		return frappe.get_all("Item", filters=item_filters, pluck="name")

	def has_item_filters(self):
		if self.filtered_item_codes is not None:
			return True
		return self.filters.doc_type in ["Sales Invoice", "Delivery Note"] and any(
			filter_by == "Order Type" for filter_by, _filter_value in self.get_secondary_filters()
		)

	def get_filtered_customer_names(self):
		customer_names = None
		for filter_by, filter_value in self.get_secondary_filters():
			matching_customers = None
			if filter_by == "Customer":
				matching_customers = {filter_value}
			elif filter_by in ["Region", "District", "Route"]:
				matching_customers = set(
					frappe.get_all(
						"Customer", filters={filter_by.lower(): filter_value}, pluck="name"
					)
				)
			elif filter_by == "Sales Person":
				matching_customers = set(
					frappe.get_all(
						"Sales Team",
						filters={"parenttype": "Customer", "sales_person": filter_value},
						pluck="parent",
					)
				)
			if matching_customers is not None:
				customer_names = (
					matching_customers
					if customer_names is None
					else customer_names.intersection(matching_customers)
				)

		if customer_names is None:
			return None
		return list(customer_names)

	def apply_secondary_item_query_filter(self, query, doctype, doctype_item):
		if self.filtered_customer_names is not None:
			query = query.where(doctype.customer.isin(self.filtered_customer_names or [""]))

		for filter_by, filter_value in self.get_secondary_filters():
			if filter_by == "Customer Group":
				query = query.where(doctype.customer_group == filter_value)
			elif filter_by == "Project":
				query = query.where(doctype.project == filter_value)
			elif filter_by == "Order Type":
				if self.filters.doc_type == "Sales Order":
					query = query.where(doctype.order_type == filter_value)
					continue

				sales_orders = frappe.get_all(
					"Sales Order",
					filters={"docstatus": 1, "order_type": filter_value},
					pluck="name",
				)
				if self.filters.doc_type == "Sales Invoice":
					query = query.where(doctype_item.sales_order.isin(sales_orders or [""]))
				elif self.filters.doc_type == "Delivery Note":
					query = query.where(doctype_item.against_sales_order.isin(sales_orders or [""]))

		return query

	def add_secondary_document_filters(self, filters):
		if self.filtered_customer_names is not None:
			filters["customer"] = ["in", self.filtered_customer_names or [""]]

		for filter_by, filter_value in self.get_secondary_filters():
			fieldname = {
				"Customer Group": "customer_group",
				"Project": "project",
			}.get(filter_by)
			if fieldname:
				filters[fieldname] = filter_value
			elif filter_by == "Order Type" and self.filters.doc_type == "Sales Order":
				filters["order_type"] = filter_value

		return filters

	def apply_secondary_header_query_filter(self, query, doctype):
		if self.filtered_customer_names is not None:
			query = query.where(doctype.customer.isin(self.filtered_customer_names or [""]))

		for filter_by, filter_value in self.get_secondary_filters():
			if filter_by == "Customer Group":
				query = query.where(doctype.customer_group == filter_value)
			elif filter_by == "Project":
				query = query.where(doctype.project == filter_value)
			elif filter_by == "Order Type" and self.filters.doc_type == "Sales Order":
				query = query.where(doctype.order_type == filter_value)
		return query

	def update_company_list_for_parent_company(self):
		company_list = [self.filters.get("company")]

		selected_company = self.filters.get("company")
		if (
			selected_company
			and self.filters.get("show_aggregate_value_from_subsidiary_companies")
			and frappe.db.get_value("Company", selected_company, "is_group")
		):
			lft, rgt = frappe.db.get_value("Company", selected_company, ["lft", "rgt"])
			child_companies = frappe.db.get_list(
				"Company", filters={"lft": [">", lft], "rgt": ["<", rgt]}, pluck="name"
			)

			company_list.extend(child_companies)

		self.filters["company"] = company_list

	def run(self):
		if (
			self.filters.value_quantity == "Unique Items"
			and self.filters.tree_type not in self.unique_item_tree_types
		):
			frappe.throw(_("Unique Items is not available for the selected Tree Type"))
		if self.filters.value_quantity == "Customer Count" and self.filters.tree_type != "Item":
			frappe.throw(_("Customer Count is only available when Tree Type is Item"))

		self.update_company_list_for_parent_company()
		self.get_columns()
		self.get_data()
		self.get_chart_data()

		# Skipping total row for tree-view reports
		skip_total_row = 0

		if self.filters.tree_type in ["Supplier Group", "Item Group", "Customer Group"]:
			skip_total_row = 1

		return self.columns, self.data, None, self.chart, None, skip_total_row

	def get_columns(self):
		tree_type = self.filters.tree_type
		fieldtype = "Link"
		options = tree_type
		if tree_type in ["Region", "District", "Model", "Description"]:
			fieldtype = "Data"
			options = ""
		elif tree_type == "Order Type":
			fieldtype = "Data"
			options = ""
		elif tree_type == "Group":
			options = "Item Group"
		elif tree_type == "Route":
			options = "Territory"

		self.columns = [
			{
				"label": _(tree_type),
				"options": options,
				"fieldname": "entity",
				"fieldtype": fieldtype,
				"width": 240 if tree_type == "Description" else 140 if tree_type != "Order Type" else 200,
			}
		]
		if self.filters.tree_type in ["Customer", "Supplier", "Item"]:
			self.columns.append(
				{
					"label": _(self.filters.tree_type + " Name"),
					"fieldname": "entity_name",
					"fieldtype": "Data",
					"width": 140,
				}
			)

		if self.filters.tree_type == "Item":
			self.columns.append(
				{
					"label": _("UOM"),
					"fieldname": "stock_uom",
					"fieldtype": "Link",
					"options": "UOM",
					"width": 100,
				}
			)
			if self.filters.get("item_dimension"):
				dimension = self.filters.item_dimension
				self.columns.append(
					{
						"label": _(dimension),
						"fieldname": "item_dimension_value",
						"fieldtype": "Link" if dimension in ["Brand", "Group"] else "Data",
						"options": {"Brand": "Brand", "Group": "Item Group"}.get(dimension, ""),
						"width": 240 if dimension == "Description" else 140,
					}
				)
		if self.filters.tree_type == "Item":
			self.columns.append(
				{
					"label": _("Stock"),
					"fieldname": "stock",
					"fieldtype": "Float",
					"width": 120,
				}
			)

		for end_date in self.periodic_daterange:
			period = self.get_period(end_date)
			self.columns.append(
				{
					"label": _(period),
					"fieldname": scrub(period),
					"fieldtype": "Float",
					"width": 120,
				}
			)

		self.columns.append(
			{"label": _("Total"), "fieldname": "total", "fieldtype": "Float", "width": 120}
		)

	def get_data(self):
		if self.filters.tree_type in ["Customer", "Supplier"]:
			self.get_sales_transactions_based_on_customers_or_suppliers()
			self.get_rows()

		elif self.filters.tree_type in ["Region", "District", "Sales Person", "Route"]:
			self.get_sales_transactions_based_on_customer_dimension()
			self.get_rows()

		elif self.filters.tree_type == "Item":
			self.get_sales_transactions_based_on_items()
			self.get_item_dimension_values()
			self.get_item_stock()
			self.get_rows()

		elif self.filters.tree_type in ["Customer Group", "Supplier Group"]:
			self.get_sales_transactions_based_on_customer_or_territory_group()
			self.get_rows_by_group()

		elif self.filters.tree_type == "Item Group":
			self.get_sales_transactions_based_on_item_group()
			self.get_rows_by_group()

		elif self.filters.tree_type == "Order Type":
			if self.filters.doc_type not in ["Sales Order", "Sales Loss"]:
				self.data = []
				return
			self.get_sales_transactions_based_on_order_type()
			self.get_rows_by_group()

		elif self.filters.tree_type == "Project":
			self.get_sales_transactions_based_on_project()
			self.get_rows()

	def get_sales_transactions_based_on_order_type(self):
		if self.filters.doc_type == "Sales Loss":
			self.entries = self.get_sales_loss_entries("order_type")
			self.get_teams()
			return
		if self.has_item_filters():
			self.entries = self.get_filtered_sales_item_entries("order_type")
			self.get_teams()
			return

		if self.filters["value_quantity"] == "Value":
			value_field = "base_net_total"
		else:
			value_field = "total_qty"

		doctype = DocType(self.filters.doc_type)

		query = (
			frappe.qb.from_(doctype)
			.select(
				doctype.order_type.as_("entity"),
				doctype[self.date_field],
				doctype[value_field].as_("value_field"),
			)
			.where(
				(doctype.docstatus == 1)
				& (doctype.company.isin(self.filters.company))
				& (doctype[self.date_field].between(self.filters.from_date, self.filters.to_date))
				& (IfNull(doctype.order_type, "") != "")
			)
			.orderby(doctype.order_type)
		)
		query = self.apply_secondary_header_query_filter(query, doctype)
		self.entries = query.run(as_dict=True)

		self.get_teams()

	def get_sales_transactions_based_on_customers_or_suppliers(self):
		if self.filters.value_quantity == "Unique Items":
			self.entries = self.get_unique_item_entries("customer")
			self.entity_names = {}
			for d in self.entries:
				self.entity_names.setdefault(d.entity, d.customer_name)
			return

		if self.filters.doc_type == "Sales Loss":
			self.entries = self.get_sales_loss_entries("customer")
			self.entity_names = {}
			for d in self.entries:
				self.entity_names.setdefault(d.entity, d.customer_name)
			return
		if self.has_item_filters():
			self.entries = self.get_filtered_sales_item_entries("customer")
			self.entity_names = {}
			for d in self.entries:
				self.entity_names.setdefault(d.entity, d.customer_name)
			return

		if self.filters["value_quantity"] == "Value":
			value_field = "base_net_total as value_field"
		else:
			value_field = "total_qty as value_field"

		if self.filters.tree_type == "Customer":
			entity = "customer as entity"
			entity_name = "customer_name as entity_name"
		else:
			entity = "supplier as entity"
			entity_name = "supplier_name as entity_name"

		filters = {
			"docstatus": 1,
			"company": ["in", self.filters.company],
			self.date_field: ("between", [self.filters.from_date, self.filters.to_date]),
		}

		if self.filters.doc_type in ["Sales Invoice", "Purchase Invoice", "Payment Entry"]:
			filters.update({"is_opening": "No"})
		filters = self.add_secondary_document_filters(filters)
		self.entries = frappe.get_all(
			self.filters.doc_type, fields=[entity, entity_name, value_field, self.date_field], filters=filters
		)

		self.entity_names = {}
		for d in self.entries:
			self.entity_names.setdefault(d.entity, d.entity_name)

	def get_sales_transactions_based_on_customer_dimension(self):
		if self.filters.value_quantity == "Unique Items":
			transactions = self.get_unique_item_entries()
		elif self.filters.doc_type == "Sales Loss":
			transactions = self.get_sales_loss_entries()
		elif self.has_item_filters():
			transactions = self.get_filtered_sales_item_entries()
		else:
			value_field = "base_net_total as value_field"
			if self.filters["value_quantity"] != "Value":
				value_field = "total_qty as value_field"

			filters = {
				"docstatus": 1,
				"company": ["in", self.filters.company],
				self.date_field: ("between", [self.filters.from_date, self.filters.to_date]),
			}
			if self.filters.doc_type == "Sales Invoice":
				filters["is_opening"] = "No"
			filters = self.add_secondary_document_filters(filters)

			transactions = frappe.get_all(
				self.filters.doc_type,
				fields=["customer", value_field, self.date_field],
				filters=filters,
			)
		customer_names = list({d.customer for d in transactions if d.customer})
		if not customer_names:
			self.entries = []
			return

		if self.filters.tree_type in ["Region", "District", "Route"]:
			fieldname = self.filters.tree_type.lower()
			customer_values = frappe.get_all(
				"Customer",
				filters={"name": ["in", customer_names]},
				fields=["name", fieldname],
			)
			value_by_customer = {d.name: d.get(fieldname) for d in customer_values}
			for transaction in transactions:
				transaction.entity = value_by_customer.get(transaction.customer) or _("Not Set")
			self.entries = transactions
			return

		sales_teams = frappe.get_all(
			"Sales Team",
			filters={"parent": ["in", customer_names], "parenttype": "Customer"},
			fields=["parent", "sales_person", "allocated_percentage"],
			order_by="idx",
		)
		teams_by_customer = frappe._dict()
		for row in sales_teams:
			teams_by_customer.setdefault(row.parent, []).append(row)

		self.entries = []
		for transaction in transactions:
			customer_team = teams_by_customer.get(transaction.customer) or []
			if not customer_team:
				transaction.entity = _("Not Set")
				self.entries.append(transaction)
				continue

			for team_member in customer_team:
				entry = frappe._dict(transaction.copy())
				entry.entity = team_member.sales_person
				entry.value_field = flt(entry.value_field) * flt(team_member.allocated_percentage) / 100
				self.entries.append(entry)

	def get_sales_transactions_based_on_items(self):
		if self.filters.doc_type == "Sales Loss":
			self.entries = self.get_sales_loss_entries("item_code")
			self.entity_names = {}
			for d in self.entries:
				self.entity_names.setdefault(d.entity, d.item_name)
			return
		if self.has_item_filters():
			self.entries = self.get_filtered_sales_item_entries("item_code")
			self.entity_names = {}
			for d in self.entries:
				self.entity_names.setdefault(d.entity, d.item_name)
			return

		if self.filters["value_quantity"] == "Value":
			value_field = "base_net_amount"
		else:
			value_field = "stock_qty"

		doctype = DocType(self.filters.doc_type)
		doctype_item = DocType(f"{self.filters.doc_type} Item")

		query = (
			frappe.qb.from_(doctype_item)
			.join(doctype)
			.on(doctype.name == doctype_item.parent)
			.select(
				doctype_item.item_code.as_("entity"),
				doctype_item.item_code,
				doctype.customer,
				doctype_item.item_name.as_("entity_name"),
				doctype_item.stock_uom,
				doctype_item[value_field].as_("value_field"),
				doctype[self.date_field],
			)
			.where(
				(doctype_item.docstatus == 1)
				& (doctype.company.isin(self.filters.company))
				& (doctype[self.date_field].between(self.filters.from_date, self.filters.to_date))
			)
		)
		query = self.apply_secondary_item_query_filter(query, doctype, doctype_item)
		self.entries = query.run(as_dict=True)

		self.entity_names = {}
		for d in self.entries:
			self.entity_names.setdefault(d.entity, d.entity_name)

	def get_item_dimension_values(self):
		self.item_dimension_by_entity = frappe._dict()
		if not self.filters.get("item_dimension"):
			return

		item_codes = list({d.entity for d in self.entries if d.entity})
		if not item_codes:
			return
		fieldname = {
			"Brand": "brand",
			"Model": "custom_model",
			"Description": "description",
			"Group": "item_group",
		}[self.filters.item_dimension]
		items = frappe.get_all(
			"Item",
			filters={"name": ["in", item_codes]},
			fields=["name", fieldname],
		)
		value_by_item = {d.name: d.get(fieldname) for d in items}
		for item_code in item_codes:
			value = value_by_item.get(item_code)
			if fieldname == "description" and value:
				value = strip_html(value).strip()
			self.item_dimension_by_entity[item_code] = value or _("Not Set")

	def get_item_stock(self):
		item_to_entity = {}
		for entry in self.entries:
			item_code = entry.get("item_code") or entry.get("entity")
			if item_code:
				item_to_entity[item_code] = entry.entity

		self.stock_by_entity = frappe._dict()
		if not item_to_entity:
			return

		stock_rows = frappe.get_all(
			"Bin",
			filters={
				"item_code": ["in", list(item_to_entity)],
				"warehouse": ["in", self.stock_warehouses],
			},
			fields=["item_code", "sum(actual_qty) as actual_qty"],
			group_by="item_code",
		)
		stock_by_item = {d.item_code: flt(d.actual_qty) for d in stock_rows}
		for item_code, entity in item_to_entity.items():
			self.stock_by_entity.setdefault(entity, 0.0)
			self.stock_by_entity[entity] += stock_by_item.get(item_code, 0.0)

	def get_sales_transactions_based_on_customer_or_territory_group(self):
		if self.filters.doc_type == "Sales Loss":
			entity_field = {
				"Customer Group": "customer_group",
				"Territory": "territory",
			}.get(self.filters.tree_type)
			self.entries = self.get_sales_loss_entries(entity_field)
			self.get_groups()
			return
		if self.has_item_filters():
			entity_field = {
				"Customer Group": "customer_group",
				"Territory": "territory",
			}.get(self.filters.tree_type)
			self.entries = self.get_filtered_sales_item_entries(entity_field)
			self.get_groups()
			return

		if self.filters["value_quantity"] == "Value":
			value_field = "base_net_total as value_field"
		else:
			value_field = "total_qty as value_field"

		if self.filters.tree_type == "Customer Group":
			entity_field = "customer_group as entity"
		elif self.filters.tree_type == "Supplier Group":
			entity_field = "supplier as entity"
			self.get_supplier_parent_child_map()
		else:
			entity_field = "territory as entity"

		filters = {
			"docstatus": 1,
			"company": ["in", self.filters.company],
			self.date_field: ("between", [self.filters.from_date, self.filters.to_date]),
		}

		if self.filters.doc_type in ["Sales Invoice", "Purchase Invoice", "Payment Entry"]:
			filters.update({"is_opening": "No"})
		filters = self.add_secondary_document_filters(filters)
		self.entries = frappe.get_all(
			self.filters.doc_type,
			fields=[entity_field, value_field, self.date_field],
			filters=filters,
		)
		self.get_groups()

	def get_sales_transactions_based_on_item_group(self):
		if self.filters.doc_type == "Sales Loss":
			self.entries = self.get_sales_loss_entries("item_group")
			self.get_groups()
			return
		if self.has_item_filters():
			self.entries = self.get_filtered_sales_item_entries("item_group")
			self.get_groups()
			return

		if self.filters["value_quantity"] == "Value":
			value_field = "base_net_amount"
		else:
			value_field = "qty"

		doctype = DocType(self.filters.doc_type)
		doctype_item = DocType(f"{self.filters.doc_type} Item")

		query = (
			frappe.qb.from_(doctype_item)
			.join(doctype)
			.on(doctype.name == doctype_item.parent)
			.select(
				doctype_item.item_group.as_("entity"),
				doctype_item[value_field].as_("value_field"),
				doctype[self.date_field],
			)
			.where(
				(doctype_item.docstatus == 1)
				& (doctype.company.isin(self.filters.company))
				& (doctype[self.date_field].between(self.filters.from_date, self.filters.to_date))
			)
		)
		query = self.apply_secondary_item_query_filter(query, doctype, doctype_item)
		self.entries = query.run(as_dict=True)

		self.get_groups()

	def get_sales_transactions_based_on_project(self):
		if self.filters.doc_type == "Sales Loss":
			self.entries = self.get_sales_loss_entries("project", require_nonempty=True)
			return
		if self.has_item_filters():
			self.entries = self.get_filtered_sales_item_entries("project", require_nonempty=True)
			return

		if self.filters["value_quantity"] == "Value":
			value_field = "base_net_total as value_field"
		else:
			value_field = "total_qty as value_field"

		entity = "project as entity"

		filters = {
			"docstatus": 1,
			"company": ["in", self.filters.company],
			"project": ["!=", ""],
			self.date_field: ("between", [self.filters.from_date, self.filters.to_date]),
		}

		if self.filters.doc_type in ["Sales Invoice", "Purchase Invoice", "Payment Entry"]:
			filters.update({"is_opening": "No"})
		filters = self.add_secondary_document_filters(filters)
		self.entries = frappe.get_all(
			self.filters.doc_type, fields=[entity, value_field, self.date_field], filters=filters
		)

	def get_unique_item_entries(self, entity_field=None):
		if not hasattr(self, "unique_item_entries"):
			if self.filters.doc_type == "Sales Loss":
				self.unique_item_entries = self.get_sales_loss_entries()
			else:
				doctype = DocType(self.filters.doc_type)
				doctype_item = DocType(f"{self.filters.doc_type} Item")
				query = (
					frappe.qb.from_(doctype_item)
					.join(doctype)
					.on(doctype.name == doctype_item.parent)
					.select(
						doctype.customer,
						doctype.customer_name,
						doctype_item.item_code,
						doctype[self.date_field],
					)
					.where(
						(doctype_item.docstatus == 1)
						& (doctype.company.isin(self.filters.company))
						& (doctype[self.date_field].between(self.filters.from_date, self.filters.to_date))
					)
				)
				if self.filters.doc_type == "Sales Invoice":
					query = query.where(doctype.is_opening == "No")
				if self.filtered_item_codes is not None:
					query = query.where(doctype_item.item_code.isin(self.filtered_item_codes or [""]))
				query = self.apply_secondary_item_query_filter(query, doctype, doctype_item)
				self.unique_item_entries = query.run(as_dict=True)

		entries = []
		for source in self.unique_item_entries:
			if not source.item_code:
				continue
			entry = frappe._dict(source.copy())
			entry.value_field = 1
			if entity_field:
				entry.entity = source.get(entity_field)
			entries.append(entry)

		return entries

	def get_filtered_sales_item_entries(self, entity_field=None, require_nonempty=False):
		if not hasattr(self, "filtered_sales_item_entries"):
			self.filtered_sales_item_entries = []

			doctype = DocType(self.filters.doc_type)
			doctype_item = DocType(f"{self.filters.doc_type} Item")
			value_field = (
				doctype_item.base_net_amount
				if self.filters["value_quantity"] == "Value"
				else doctype_item.stock_qty
			)
			query = (
				frappe.qb.from_(doctype_item)
				.join(doctype)
				.on(doctype.name == doctype_item.parent)
				.select(
					doctype.customer,
					doctype.customer_name,
					doctype.customer_group,
					doctype.territory,
					doctype.project,
					doctype[self.date_field],
					doctype_item.item_code,
					doctype_item.item_name,
					doctype_item.item_group,
					doctype_item.stock_uom,
					value_field.as_("value_field"),
				)
				.where(
					(doctype_item.docstatus == 1)
					& (doctype.company.isin(self.filters.company))
					& (doctype[self.date_field].between(self.filters.from_date, self.filters.to_date))
				)
			)
			if self.filtered_item_codes is not None:
				query = query.where(doctype_item.item_code.isin(self.filtered_item_codes or [""]))
			if self.filters.doc_type == "Sales Invoice":
				query = query.where(doctype.is_opening == "No")
			if self.filters.doc_type == "Sales Order":
				query = query.select(doctype.order_type)
			query = self.apply_secondary_item_query_filter(query, doctype, doctype_item)

			self.filtered_sales_item_entries = query.run(as_dict=True)

		entries = []
		for source in self.filtered_sales_item_entries:
			if require_nonempty and not source.get(entity_field):
				continue
			entry = frappe._dict(source.copy())
			if entity_field:
				entry.entity = source.get(entity_field)
			entries.append(entry)

		return entries

	def get_sales_loss_entries(self, entity_field=None, require_nonempty=False):
		if not hasattr(self, "sales_loss_entries"):
			order_filters = {
				"docstatus": 1,
				"company": ["in", self.filters.company],
				"transaction_date": (
					"between",
					[self.filters.from_date, self.filters.to_date],
				),
			}
			if self.filtered_customer_names is not None:
				order_filters["customer"] = ["in", self.filtered_customer_names or [""]]
			for filter_by, filter_value in self.get_secondary_filters():
				order_field = {
					"Customer Group": "customer_group",
					"Project": "project",
					"Order Type": "order_type",
				}.get(filter_by)
				if order_field:
					order_filters[order_field] = filter_value

			orders = frappe.get_all(
				"Sales Order",
				filters=order_filters,
				fields=[
					"name",
					"customer",
					"customer_name",
					"customer_group",
					"territory",
					"order_type",
					"project",
					"transaction_date",
				],
			)
			order_by_name = {d.name: d for d in orders}
			order_names = list(order_by_name)
			self.sales_loss_entries = []
			if not order_names:
				return []

			invoiced_orders = set(
				frappe.get_all(
					"Sales Invoice Item",
					filters={"docstatus": 1, "sales_order": ["in", order_names]},
					pluck="sales_order",
					distinct=True,
				)
			)
			if not invoiced_orders:
				return []

			item_filters = {"parent": ["in", list(invoiced_orders)]}
			if self.filtered_item_codes is not None:
				item_filters["item_code"] = ["in", self.filtered_item_codes or [""]]

			order_items = frappe.get_all(
				"Sales Order Item",
				filters=item_filters,
				fields=[
					"name",
					"parent",
					"item_code",
					"item_name",
					"item_group",
					"stock_uom",
					"qty",
					"stock_qty",
					"base_net_amount",
				],
			)
			item_by_name = {d.name: d for d in order_items}
			items_by_order_and_code = frappe._dict()
			for item in order_items:
				items_by_order_and_code.setdefault((item.parent, item.item_code), []).append(item.name)

			invoiced_qty_by_item = frappe._dict()
			if order_items:
				invoice_items = frappe.get_all(
					"Sales Invoice Item",
					filters={"docstatus": 1, "sales_order": ["in", list(invoiced_orders)]},
					fields=["sales_order", "so_detail", "item_code", "qty"],
				)
				for invoice_item in invoice_items:
					order_item = invoice_item.so_detail if invoice_item.so_detail in item_by_name else None
					if not order_item:
						matching_items = items_by_order_and_code.get(
							(invoice_item.sales_order, invoice_item.item_code), []
						)
						if len(matching_items) == 1:
							order_item = matching_items[0]

					if order_item:
						invoiced_qty_by_item.setdefault(order_item, 0.0)
						invoiced_qty_by_item[order_item] += flt(invoice_item.qty)

			for item in order_items:
				ordered_qty = flt(item.qty)
				if not ordered_qty:
					continue

				loss_qty = max(ordered_qty - invoiced_qty_by_item.get(item.name, 0), 0)
				if not loss_qty:
					continue

				order = order_by_name[item.parent]
				loss_ratio = loss_qty / ordered_qty
				value_field = (
					flt(item.base_net_amount) * loss_ratio
					if self.filters["value_quantity"] == "Value"
					else flt(item.stock_qty) * loss_ratio
				)
				self.sales_loss_entries.append(
					frappe._dict(
						customer=order.customer,
						customer_name=order.customer_name,
						customer_group=order.customer_group,
						territory=order.territory,
						order_type=order.order_type,
						project=order.project,
						item_code=item.item_code,
						item_name=item.item_name,
						item_group=item.item_group,
						stock_uom=item.stock_uom,
						transaction_date=order.transaction_date,
						value_field=value_field,
					)
				)

		entries = []
		for source in self.sales_loss_entries:
			if require_nonempty and not source.get(entity_field):
				continue
			entry = frappe._dict(source.copy())
			if entity_field:
				entry.entity = source.get(entity_field)
			entries.append(entry)

		return entries

	def get_rows(self):
		self.data = []
		self.get_periodic_data()

		for entity, period_data in self.entity_periodic_data.items():
			row = {
				"entity": entity,
				"entity_name": self.entity_names.get(entity) if hasattr(self, "entity_names") else None,
			}
			total = 0
			for end_date in self.periodic_daterange:
				period = self.get_period(end_date)
				amount = flt(period_data.get(period, 0.0))
				row[scrub(period)] = amount
				total += amount

			row["total"] = (
				len(self.entity_unique_values.get(entity, set()))
				if self.filters.value_quantity in ["Unique Items", "Customer Count"]
				else total
			)
			if self.filters.tree_type in ["Region", "District", "Sales Person", "Route"] and not row["total"]:
				continue
			if self.filters.tree_type == "Item":
				row["stock"] = self.stock_by_entity.get(entity, 0.0)
				if self.filters.get("item_dimension"):
					row["item_dimension_value"] = self.item_dimension_by_entity.get(
						entity, _("Not Set")
					)

			if self.filters.tree_type == "Item":
				row["stock_uom"] = period_data.get("stock_uom")

			self.data.append(row)

	def get_rows_by_group(self):
		self.get_periodic_data()
		out = []

		for d in reversed(self.group_entries):
			row = {"entity": d.name, "indent": self.depth_map.get(d.name)}
			total = 0
			for end_date in self.periodic_daterange:
				period = self.get_period(end_date)
				amount = flt(self.entity_periodic_data.get(d.name, {}).get(period, 0.0))
				row[scrub(period)] = amount
				if d.parent and (self.filters.tree_type != "Order Type" or d.parent == "Order Types"):
					self.entity_periodic_data.setdefault(d.parent, frappe._dict()).setdefault(period, 0.0)
					self.entity_periodic_data[d.parent][period] += amount
				total += amount

			row["total"] = total
			out = [row, *out]

		self.data = out

	def get_periodic_data(self):
		self.entity_periodic_data = frappe._dict()
		if self.filters.value_quantity in ["Unique Items", "Customer Count"]:
			distinct_field = "item_code" if self.filters.value_quantity == "Unique Items" else "customer"
			period_items = frappe._dict()
			self.entity_unique_values = frappe._dict()
			for d in self.entries:
				distinct_value = d.get(distinct_field)
				if not distinct_value:
					continue
				period = self.get_period(d.get(self.date_field))
				period_items.setdefault(d.entity, frappe._dict()).setdefault(period, set()).add(
					distinct_value
				)
				self.entity_unique_values.setdefault(d.entity, set()).add(distinct_value)

			for entity, periods in period_items.items():
				self.entity_periodic_data[entity] = frappe._dict(
					{period: len(items) for period, items in periods.items()}
				)
			return

		for d in self.entries:
			if self.filters.tree_type == "Supplier Group":
				d.entity = self.parent_child_map.get(d.entity)
			period = self.get_period(d.get(self.date_field))
			self.entity_periodic_data.setdefault(d.entity, frappe._dict()).setdefault(period, 0.0)
			self.entity_periodic_data[d.entity][period] += flt(d.value_field)

			if self.filters.tree_type == "Item":
				self.entity_periodic_data[d.entity]["stock_uom"] = d.stock_uom

	def get_period(self, posting_date):
		if self.filters.range == "Daily":
			period = _("Day {0}").format(posting_date.strftime("%d %b %Y"))
		elif self.filters.range == "Weekly":
			period = _("Week {0} {1}").format(str(posting_date.isocalendar()[1]), str(posting_date.year))
		elif self.filters.range == "Monthly":
			period = _(str(self.months[posting_date.month - 1])) + " " + str(posting_date.year)
		elif self.filters.range == "Quarterly":
			period = _("Quarter {0} {1}").format(
				str(((posting_date.month - 1) // 3) + 1), str(posting_date.year)
			)
		else:
			year = get_fiscal_year(posting_date, company=self.filters.company[0])
			period = str(year[0])
		return period

	def get_period_date_ranges(self):
		from dateutil.relativedelta import MO, relativedelta

		from_date, to_date = getdate(self.filters.from_date), getdate(self.filters.to_date)
		if self.filters.range == "Daily":
			self.periodic_daterange = []
			while from_date <= to_date:
				self.periodic_daterange.append(from_date)
				from_date = add_days(from_date, 1)
			return

		increment = {"Monthly": 1, "Quarterly": 3, "Half-Yearly": 6, "Yearly": 12}.get(self.filters.range, 1)

		if self.filters.range in ["Monthly", "Quarterly"]:
			from_date = from_date.replace(day=1)
		elif self.filters.range == "Yearly":
			from_date = get_fiscal_year(from_date)[1]
		else:
			from_date = from_date + relativedelta(from_date, weekday=MO(-1))

		self.periodic_daterange = []
		for _dummy in range(1, 53):
			if self.filters.range == "Weekly":
				period_end_date = add_days(from_date, 6)
			else:
				period_end_date = add_to_date(from_date, months=increment, days=-1)

			if period_end_date > to_date:
				period_end_date = to_date

			self.periodic_daterange.append(period_end_date)

			from_date = add_days(period_end_date, 1)
			if period_end_date == to_date:
				break

	def get_groups(self):
		if self.filters.tree_type == "Territory":
			parent = "parent_territory"
		if self.filters.tree_type == "Customer Group":
			parent = "parent_customer_group"
		if self.filters.tree_type == "Item Group":
			parent = "parent_item_group"
		if self.filters.tree_type == "Supplier Group":
			parent = "parent_supplier_group"

		self.depth_map = frappe._dict()

		self.group_entries = frappe.db.sql(
			f"""select name, lft, rgt , {parent} as parent
			from `tab{self.filters.tree_type}` order by lft""",
			as_dict=1,
		)

		for d in self.group_entries:
			if d.parent:
				self.depth_map.setdefault(d.name, self.depth_map.get(d.parent) + 1)
			else:
				self.depth_map.setdefault(d.name, 0)

	def get_teams(self):
		self.depth_map = frappe._dict()
		doctype = "Sales Order" if self.filters.doc_type == "Sales Loss" else self.filters.doc_type

		self.group_entries = frappe.db.sql(
			f""" select * from (select "Order Types" as name, 0 as lft,
			2 as rgt, '' as parent union select distinct order_type as name, 1 as lft, 1 as rgt, "Order Types" as parent
			from `tab{doctype}` where ifnull(order_type, '') != '') as b order by lft, name
			""",
			as_dict=1,
		)

		for d in self.group_entries:
			if d.parent:
				self.depth_map.setdefault(d.name, self.depth_map.get(d.parent) + 1)
			else:
				self.depth_map.setdefault(d.name, 0)

	def get_supplier_parent_child_map(self):
		self.parent_child_map = frappe._dict(
			frappe.db.sql(""" select name, supplier_group from `tabSupplier`""")
		)

	def get_chart_data(self):
		length = len(self.columns)

		if self.filters.tree_type in ["Customer", "Supplier"]:
			labels = [d.get("label") for d in self.columns[2 : length - 1]]
		elif self.filters.tree_type == "Item":
			start = 5 if self.filters.get("item_dimension") else 4
			labels = [d.get("label") for d in self.columns[start : length - 1]]
		else:
			labels = [d.get("label") for d in self.columns[1 : length - 1]]

		datasets = []
		for curve in self.data:
			data = {
				"name": curve.get("entity_name") or curve["entity"],
				"values": [curve.get(scrub(label), 0) for label in labels],
			}
			if self.filters.curves == "non-zeros" and not sum(data["values"]):
				continue
			elif self.filters.curves == "total" and "indent" in curve:
				if curve["indent"] == 0:
					datasets.append(data)
			elif self.filters.curves == "total":
				if datasets:
					a = [
						data["values"][idx] + datasets[0]["values"][idx] for idx in range(len(data["values"]))
					]
					datasets[0]["values"] = a
				else:
					datasets.append(data)
					datasets[0]["name"] = _("Total")
			else:
				datasets.append(data)

		self.chart = {"data": {"labels": labels, "datasets": datasets}, "type": "line"}

		if self.filters["value_quantity"] == "Value":
			self.chart["fieldtype"] = "Currency"
		else:
			self.chart["fieldtype"] = "Float"
