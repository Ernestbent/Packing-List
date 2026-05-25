## Copyright (c) 2024, Your Company and contributors
## For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.utils import flt, cint

WAREHOUSE_COLUMNS = [
    {
        "fieldname": "container_1_qty",
        "label": _("Container 1"),
        "warehouse": "Cont. No. 1 = MAEU-8382503 - APL",
    },
    {
        "fieldname": "container_2_qty",
        "label": _("Container 2"),
        "warehouse": "Cont. No. 2 = FTBU-8875500 - APL",
    },
    {
        "fieldname": "main_location_qty",
        "label": _("Main Location"),
        "warehouse": "Main Loc - APL",
    },
]

def execute(filters=None):
    columns, data = get_columns(), get_data(filters)
    return columns, data

def get_columns():
    return [
        {
            "fieldname": "item_code",
            "label": _("Item Code"),
            "fieldtype": "Link",
            "options": "Item",
            "width": 150
        },
        {
            "fieldname": "item_description",
            "label": _("Item Description"),
            "fieldtype": "Data",
            "width": 300
        },
        {
            "fieldname": "brand",
            "label": _("Brand"),
            "fieldtype": "Link",
            "options": "Brand",
            "width": 120
        },
        {
            "fieldname": "standard_buying",
            "label": _("Standard Buying"),
            "fieldtype": "Currency",
            "options": "currency",
            "width": 130,
            "precision": 0
        },
        {
            "fieldname": "standard_selling",
            "label": _("Standard Selling"),
            "fieldtype": "Currency",
            "options": "currency",
            "width": 130,
            "precision": 0
        },
        {
            "fieldname": "stockist_selling",
            "label": _("Stockist Selling"),
            "fieldtype": "Currency",
            "options": "currency",
            "width": 130,
            "precision": 0
        },
        {
            "fieldname": "distributor_price",
            "label": _("Distributor Price"),
            "fieldtype": "Currency",
            "options": "currency",
            "width": 130,
            "precision": 0
        },
        {
            "fieldname": "retailer_price",
            "label": _("Retailer Price"),
            "fieldtype": "Currency",
            "options": "currency",
            "width": 130,
            "precision": 0
        },
        {
            "fieldname": "verma_price",
            "label": _("Verma Price List"),
            "fieldtype": "Currency",
            "options": "currency",
            "width": 130,
            "precision": 0
        },
        {
            "fieldname": "container_1_qty",
            "label": _("Container 1"),
            "fieldtype": "Int",
            "width": 110,
        },
        {
            "fieldname": "container_2_qty",
            "label": _("Container 2"),
            "fieldtype": "Int",
            "width": 110,
        },
        {
            "fieldname": "main_location_qty",
            "label": _("Main Location"),
            "fieldtype": "Int",
            "width": 120,
        },
        {
            "fieldname": "grand_total",
            "label": _("Grand Total"),
            "fieldtype": "Currency",
            "options": "currency",
            "width": 130,
            "precision": 0
        },
        {
            "fieldname": "calculated_stockist",
            "label": _("Stockist Calculated"),
            "fieldtype": "Check",
            "width": 100,
            "hidden": 1
        },
        {
            "fieldname": "calculated_distributor",
            "label": _("Distributor Calculated"),
            "fieldtype": "Check",
            "width": 100,
            "hidden": 1
        },
        {
            "fieldname": "calculated_retailer",
            "label": _("Retailer Calculated"),
            "fieldtype": "Check",
            "width": 100,
            "hidden": 1
        }
    ]

def get_data(filters):
    data = []

    ## Build item filters
    item_filters = {"disabled": 0}
    if filters.get("item_code"):
        item_filters["item_code"] = filters.get("item_code")
    if filters.get("brand"):
        item_filters["brand"] = filters.get("brand")

    ## Get items from database
    items = frappe.db.get_all("Item",
        filters=item_filters,
        fields=["item_code", "item_name", "description", "brand"],
        order_by="item_code",
        limit_page_length=2000
    )

    if not items:
        frappe.msgprint(_("No items found with the selected filters"))
        return data

    ## Get all item prices from database
    item_prices = frappe.db.get_all("Item Price",
        fields=["item_code", "price_list", "price_list_rate"],
        limit_page_length=50000
    )

    ## Organize prices by item code and price list name
    price_map = {}
    for price in item_prices:
        if price.item_code not in price_map:
            price_map[price.item_code] = {}
        price_map[price.item_code][price.price_list] = price.price_list_rate

    stock_qty_map = get_stock_qty_map([item.item_code for item in items])

    ## Process each item and calculate prices
    for item in items:
        row = {
            "item_code": item.item_code,
            "item_description": item.description or item.item_name,
            "brand": item.brand,
            "calculated_stockist": 0,
            "calculated_distributor": 0,
            "calculated_retailer": 0
        }

        ## Get Standard Buying Price from price list
        standard_buying = get_price(price_map, item.item_code, "Standard Buying")
        row["standard_buying"] = int(standard_buying) if standard_buying else None

        ## Get Standard Selling Price from price list
        standard_selling = get_price(price_map, item.item_code, "Standard Selling")
        row["standard_selling"] = int(standard_selling) if standard_selling else None

        ## Stockist Selling: 5% discount from Standard Selling or use explicit price
        stockist_selling = get_price(price_map, item.item_code, "Stockist Selling")
        if stockist_selling:
            row["stockist_selling"] = int(stockist_selling)
        elif row["standard_selling"]:
            calculated = int(row["standard_selling"] * 0.95)
            row["stockist_selling"] = calculated
            row["calculated_stockist"] = 1
        else:
            row["stockist_selling"] = None

        ## Distributor Price: 5% discount from Standard Selling or use explicit price
        distributor_price = get_price(price_map, item.item_code, "Distributor Price")
        if distributor_price:
            row["distributor_price"] = int(distributor_price)
        elif row["standard_selling"]:
            final_price = int(row["standard_selling"] * 0.95)
            row["distributor_price"] = final_price
            row["calculated_distributor"] = 1
        else:
            row["distributor_price"] = None

        ## Retailer Price: 20% markup from Standard Selling or use explicit price
        retailer_price = get_price(price_map, item.item_code, "Retail Walking")
        if retailer_price:
            row["retailer_price"] = int(retailer_price)
        elif row["standard_selling"]:
            calculated = int(row["standard_selling"] * 1.20)
            row["retailer_price"] = calculated
            row["calculated_retailer"] = 1
        else:
            row["retailer_price"] = None

        ## Get Verma Price List from price list
        verma_price = get_price(price_map, item.item_code, "Verma Price List")
        row["verma_price"] = int(verma_price) if verma_price else None

        for warehouse_column in WAREHOUSE_COLUMNS:
            qty = stock_qty_map.get(item.item_code, {}).get(warehouse_column["warehouse"], 0)
            row[warehouse_column["fieldname"]] = cint(qty)

        ## Calculate Grand Total: sum of all prices for this item
        grand_total = 0
        if row["standard_buying"]:
            grand_total += row["standard_buying"]
        if row["standard_selling"]:
            grand_total += row["standard_selling"]
        if row["stockist_selling"]:
            grand_total += row["stockist_selling"]
        if row["distributor_price"]:
            grand_total += row["distributor_price"]
        if row["retailer_price"]:
            grand_total += row["retailer_price"]
        if row["verma_price"]:
            grand_total += row["verma_price"]

        row["grand_total"] = int(grand_total) if grand_total > 0 else None

        ## Filter out items with no prices if option is selected
        if filters.get("show_only_with_prices"):
            has_price = False
            if row["standard_buying"] or row["standard_selling"] or \
               row["stockist_selling"] or row["distributor_price"] or \
               row["retailer_price"] or row["verma_price"]:
                has_price = True
            if not has_price:
                continue

        data.append(row)

    return data

def get_price(price_map, item_code, price_list):
    ## Retrieve price from price map by item code and price list name
    if item_code in price_map and price_list in price_map[item_code]:
        return price_map[item_code][price_list]
    return None

def get_stock_qty_map(item_codes):
    if not item_codes:
        return {}

    warehouses = [column["warehouse"] for column in WAREHOUSE_COLUMNS]
    bins = frappe.db.get_all(
        "Bin",
        filters={
            "item_code": ["in", item_codes],
            "warehouse": ["in", warehouses],
        },
        fields=["item_code", "warehouse", "actual_qty"],
        limit_page_length=50000,
    )

    stock_qty_map = {}
    for bin_row in bins:
        stock_qty_map.setdefault(bin_row.item_code, {})
        stock_qty_map[bin_row.item_code][bin_row.warehouse] = (
            stock_qty_map[bin_row.item_code].get(bin_row.warehouse, 0)
            + flt(bin_row.actual_qty)
        )

    return stock_qty_map
