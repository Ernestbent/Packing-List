import frappe
from frappe.utils import flt


LIMIT_DOCTYPE_CANDIDATES = (
    "Sales Order Item Limit",
    "Sales Order Qty Limit",
    "Item Order Limit",
    "Sales Order Limit",
)
ITEM_FIELD_CANDIDATES = ("item_code", "item")
QTY_FIELD_CANDIDATES = ("maximum_qty", "max_qty", "qty")
ACTIVE_FIELD_CANDIDATES = ("is_active", "enabled", "active")


def validate_sales_order_item_limits(doc):
    if not doc.get("items"):
        return

    limits = get_item_limits()
    if not limits:
        return

    ordered_qty_by_item = {}

    for row in doc.items:
        item_code = row.item_code
        if item_code not in limits:
            continue

        ordered_qty_by_item[item_code] = ordered_qty_by_item.get(item_code, 0) + flt(row.qty)

    for item_code, ordered_qty in ordered_qty_by_item.items():
        max_qty = limits[item_code]
        if ordered_qty <= max_qty:
            continue

        frappe.throw(
            "Item {0} cannot be ordered above {1:g} qty in one Sales Order."
            "<br>Ordered Qty: <b>{2:g}</b>".format(item_code, max_qty, ordered_qty),
            title="Item Quantity Limit Exceeded",
        )


def get_item_limits():
    limit_doctype = get_limit_doctype()
    if not limit_doctype:
        return {}

    meta = frappe.get_meta(limit_doctype)

    item_field = get_first_existing_field(meta, ITEM_FIELD_CANDIDATES)
    qty_field = get_first_existing_field(meta, QTY_FIELD_CANDIDATES)
    active_field = get_first_existing_field(meta, ACTIVE_FIELD_CANDIDATES)

    if not item_field or not qty_field:
        return {}

    filters = {}
    if active_field:
        filters[active_field] = 1

    rows = frappe.get_all(limit_doctype, filters=filters, fields=[item_field, qty_field])

    limits = {}
    for row in rows:
        item_code = row.get(item_field)
        max_qty = flt(row.get(qty_field))
        if not item_code or max_qty <= 0:
            continue
        limits[item_code] = max_qty

    return limits


def get_limit_doctype():
    for doctype_name in LIMIT_DOCTYPE_CANDIDATES:
        if frappe.db.exists("DocType", doctype_name):
            return doctype_name

    doctypes = frappe.get_all(
        "DocType",
        filters={"module": "Autozonepro", "name": ["like", "%Limit%"]},
        pluck="name",
    )

    for doctype_name in doctypes:
        try:
            meta = frappe.get_meta(doctype_name)
        except Exception:
            continue

        item_field = get_first_existing_field(meta, ITEM_FIELD_CANDIDATES)
        qty_field = get_first_existing_field(meta, QTY_FIELD_CANDIDATES)
        if item_field and qty_field:
            return doctype_name

    return None


def get_first_existing_field(meta, candidates):
    for fieldname in candidates:
        if meta.has_field(fieldname):
            return fieldname
    return None
