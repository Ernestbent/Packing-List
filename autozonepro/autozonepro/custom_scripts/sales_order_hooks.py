import frappe
from frappe.utils import flt


EXEMPT_BOXER_CUSTOMER = "MARK SHAMBA-0787273088"
BOXER_TARGET_ITEM = "MGRT-BOXR-DX05"
BOXER_LIMIT_QTY = 26


def validate(doc, method=None):
    enforce_boxer_cash_first(doc)


def enforce_boxer_cash_first(doc):
    if doc.customer == EXEMPT_BOXER_CUSTOMER:
        return

    if not doc.customer or not doc.company or not doc.get("items"):
        return

    total_qty = 0
    total_value = 0

    for row in doc.items:
        if row.item_code == BOXER_TARGET_ITEM:
            qty = flt(row.qty)
            rate = flt(row.rate)
            total_qty += qty
            total_value += qty * rate

    if total_qty <= BOXER_LIMIT_QTY:
        return

    advance_amount = get_customer_advance_amount(doc.customer, doc.company)

    if advance_amount <= 0:
        frappe.throw(
            "Boxer DX05 ({0}): {1:g} pcs ordered requires advance payment."
            "<br><br><b>Customer must make advance payment before saving this Sales Order.</b>".format(
                BOXER_TARGET_ITEM,
                total_qty,
            ),
            title="Cash First - Payment Required",
        )

    if total_value > advance_amount:
        shortfall = total_value - advance_amount
        frappe.throw(
            "Boxer DX05: {0:g} pcs"
            "<br>Total Value: <b>{1:,.2f}</b>"
            "<br>Customer Advance: <b>{2:,.2f}</b>"
            "<br><br>Shortfall: <b>{3:,.2f}</b>"
            "<br><br>Additional advance payment required before saving.".format(
                total_qty,
                total_value,
                advance_amount,
                shortfall,
            ),
            title="Cash First - Insufficient Advance",
        )


def get_customer_advance_amount(customer, company):
    balance = frappe.db.sql(
        """
        select coalesce(sum(debit - credit), 0)
        from `tabGL Entry`
        where party_type = 'Customer'
          and party = %s
          and company = %s
          and is_cancelled = 0
        """,
        (customer, company),
    )[0][0]

    return abs(flt(balance)) if flt(balance) < 0 else 0
