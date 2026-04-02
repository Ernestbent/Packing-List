import frappe

## GitHub base URL for item images
GITHUB_BASE = "https://github.com/Ernestbent/Autozone-Professional-Limited-Images-/raw/main"

def execute(filters=None):
    ## Columns, image shown as clickable hyperlink
    columns = [
        {"fieldname": "item_code",  "label": "Item Code",  "fieldtype": "Link", "options": "Item", "width": 150},
        {"fieldname": "item_name",  "label": "Item Name",  "fieldtype": "Data", "width": 200},
        {"fieldname": "item_group", "label": "Item Group", "fieldtype": "Data", "width": 150},
        {"fieldname": "stock_uom",  "label": "UOM",        "fieldtype": "Data", "width": 80},
        {"fieldname": "image",      "label": "Image",      "fieldtype": "HTML", "width": 200},
    ]

    ## Only fetch items that have an image attached
    conditions = "WHERE disabled = 0 AND image IS NOT NULL AND image != ''"
    values = {}

    if filters:
        if filters.get("item_group"):
            conditions += " AND item_group = %(item_group)s"
            values["item_group"] = filters["item_group"]

        if filters.get("item_code"):
            conditions += " AND item_code = %(item_code)s"
            values["item_code"] = filters["item_code"]

    ## Fetch items with images only
    data = frappe.db.sql(f"""
        SELECT item_code, item_name, item_group, stock_uom, image
        FROM `tabItem`
        {conditions}
        ORDER BY item_group, item_name
    """, values=values, as_dict=True)

    for row in data:
        ## Replace / in item_code with - to match GitHub filenames
        safe_code = row["item_code"].replace("/", "-")

        ## Build GitHub URL from item_code
        url = f"{GITHUB_BASE}/{safe_code}.jpg"

        ## Wrap in clickable hyperlink opening in new tab
        row["image"] = f'<a href="{url}" target="_blank">View Image</a>'

    return columns, data