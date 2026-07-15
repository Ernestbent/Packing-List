import frappe
from frappe.utils import escape_html, flt


LIMIT_DOCTYPE_CANDIDATES = (
    "Sales Order Item Limit",
    "Sales Order Qty Limit",
    "Item Order Limit",
    "Sales Order Limit",
)
ITEM_FIELD_CANDIDATES = ("item_code", "item")
QTY_FIELD_CANDIDATES = ("maximum_qty", "max_qty", "qty")
ACTIVE_FIELD_CANDIDATES = ("is_active", "enabled", "active")

CASH_ITEMS_DOCTYPE = "Cash Items"
CASH_ITEM_EXEMPT_CUSTOMERS = {"MARK SHAMBA-0787273088"}


def validate_sales_order_item_limits(doc, method=None):
    cash_item_rules = get_cash_item_rules()
    enforce_cash_item_credit(doc, cash_item_rules)

    if not doc.get("items"):
        return

    limits = get_item_limits()
    if not limits:
        return

    ordered_qty_by_item = {}

    for row in doc.items:
        item_code = row.item_code
        if item_code in cash_item_rules:
            continue
        if item_code not in limits:
            continue

        ordered_qty_by_item[item_code] = ordered_qty_by_item.get(item_code, 0) + flt(row.qty)

    for item_code, ordered_qty in ordered_qty_by_item.items():
        max_qty = limits[item_code]
        if ordered_qty <= max_qty:
            continue

        reject_sales_order_submission(
            "Item {0} cannot be ordered above {1:g} qty in one Sales Order."
            "<br>Ordered Qty: <b>{2:g}</b>".format(item_code, max_qty, ordered_qty),
            title="Item Quantity Limit Exceeded",
        )


def enforce_cash_item_credit(doc, cash_item_rules):
    if (
        doc.customer in CASH_ITEM_EXEMPT_CUSTOMERS
        or not doc.customer
        or not doc.company
        or not doc.get("items")
        or not cash_item_rules
    ):
        return

    item_totals = {
        item_code: {"qty": 0, "value": 0}
        for item_code in cash_item_rules
    }

    for row in doc.items:
        if row.item_code not in cash_item_rules:
            continue

        qty = flt(row.qty)
        item_totals[row.item_code]["qty"] += qty
        item_totals[row.item_code]["value"] += get_row_value_in_company_currency(row, qty)

    exceeded_items = [
        {
            "item_code": item_code,
            "label": rule["label"],
            "limit_qty": rule["limit_qty"],
            "qty": item_totals[item_code]["qty"],
            "value": item_totals[item_code]["value"],
        }
        for item_code, rule in cash_item_rules.items()
        if item_totals[item_code]["qty"] > rule["limit_qty"]
    ]
    if not exceeded_items:
        return

    total_value = sum(item["value"] for item in exceeded_items)
    advance_amount = get_customer_advance_amount(
        doc.customer,
        doc.company,
        doc.transaction_date,
    )
    currency = frappe.get_cached_value("Company", doc.company, "default_currency")
    item_details = "<br>".join(
        "{0} ({1}): <b>{2:g} pcs</b> ordered; limit without advance: <b>{3:g} pcs</b>".format(
            escape_html(item["label"]),
            escape_html(item["item_code"]),
            item["qty"],
            item["limit_qty"],
        )
        for item in exceeded_items
    )

    if advance_amount <= 0:
        reject_sales_order_submission(
            "{0}<br><br><b>Advance payment is required.</b>"
            "<br>Please add advance payment or reduce the quantity.".format(
                item_details,
            ),
            title="Advance Payment Required",
        )

    if total_value > advance_amount:
        shortfall = total_value - advance_amount
        reject_sales_order_submission(
            "{0}"
            "<br><br>Total Value: <b>{1}</b>"
            "<br>Customer Advance: <b>{2}</b>"
            "<br><br>Shortfall: <b>{3}</b>"
            "<br><br>Please add the required advance or reduce the quantity.".format(
                item_details,
                frappe.utils.fmt_money(total_value, currency=currency),
                frappe.utils.fmt_money(advance_amount, currency=currency),
                frappe.utils.fmt_money(shortfall, currency=currency),
            ),
            title="Additional Advance Required",
        )


def reject_sales_order_submission(message, title):
    frappe.throw(message, title=title)


def get_cash_item_rules():
    if not frappe.db.exists("DocType", CASH_ITEMS_DOCTYPE):
        return {}

    settings = frappe.get_cached_doc(CASH_ITEMS_DOCTYPE)
    if not settings.enabled:
        return {}

    rules = {}
    for row in settings.items:
        limit_qty = flt(row.quantity)
        if not row.item or limit_qty <= 0:
            continue

        rules[row.item] = {
            "label": row.item_name or row.item,
            "limit_qty": limit_qty,
        }

    return rules


def get_row_value_in_company_currency(row, qty):
    base_net_amount = row.get("base_net_amount")
    if base_net_amount is not None:
        return flt(base_net_amount)

    base_amount = row.get("base_amount")
    if base_amount is not None:
        return flt(base_amount)

    return qty * flt(row.get("base_rate") or row.rate)


def get_customer_advance_amount(customer, company, posting_date):
    posting_date = posting_date or frappe.utils.nowdate()
    balance = frappe.db.sql(
        """
        select coalesce(sum(debit - credit), 0)
        from `tabGL Entry`
        where party_type = 'Customer'
          and party = %s
          and company = %s
          and posting_date <= %s
          and is_cancelled = 0
        """,
        (customer, company, posting_date),
    )[0][0]

    balance = flt(balance)
    return abs(balance) if balance < 0 else 0


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
