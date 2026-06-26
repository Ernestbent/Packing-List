import frappe
from frappe.utils import flt


BOXER_TARGET_ITEM = "MGRT-BOXR-DX05"
BOXER_LIMIT_QTY = 26
CASH_FIRST_ITEM_RULES = {
    BOXER_TARGET_ITEM: {
        "label": "Boxer DX05",
        "limit_qty": BOXER_LIMIT_QTY,
    },
    # "R2081001R": {
    #     "label": "R2081001R",
    #     "limit_qty": 19,
    # },
}


def validate(doc, method=None):
    enforce_boxer_cash_first(doc)


def enforce_boxer_cash_first(doc):
    ## Return early if missing core fields
    if not doc.customer or not doc.company or not doc.get("items"):
        return

    ## Calculate totals per restricted item code
    item_totals = {
        item_code: {"qty": 0, "value": 0}
        for item_code in CASH_FIRST_ITEM_RULES
    }

    for row in doc.items:
        if row.item_code in CASH_FIRST_ITEM_RULES:
            qty = flt(row.qty)
            rate = flt(row.rate)
            item_totals[row.item_code]["qty"] += qty
            item_totals[row.item_code]["value"] += qty * rate

    ## Find which items exceed their limits
    exceeded_items = [
        (item_code, item_totals[item_code]["qty"], item_totals[item_code]["value"])
        for item_code, rule in CASH_FIRST_ITEM_RULES.items()
        if item_totals[item_code]["qty"] > rule["limit_qty"]
    ]

    if not exceeded_items:
        return

    ## Get customer advance balance from GL Entry
    advance_amount = get_customer_advance_amount(doc.customer, doc.company)

    ## Validate each exceeded item against advance balance
    for item_code, total_qty, total_value in exceeded_items:
        label = CASH_FIRST_ITEM_RULES[item_code]["label"]

        if advance_amount <= 0:
            frappe.throw(
                "{0} ({1}): {2:g} pcs ordered requires advance payment."
                "<br><br><b>Customer must make advance payment before saving this Sales Order.</b>".format(
                    label,
                    item_code,
                    total_qty,
                ),
                title="Cash First - Payment Required",
            )

        if total_value > advance_amount:
            shortfall = total_value - advance_amount
            frappe.throw(
                "{0}: {1:g} pcs"
                "<br>Total Value: <b>{2:,.2f}</b>"
                "<br>Customer Advance: <b>{3:,.2f}</b>"
                "<br><br>Shortfall: <b>{4:,.2f}</b>"
                "<br><br>Additional advance payment required before saving.".format(
                    label,
                    total_qty,
                    total_value,
                    advance_amount,
                    shortfall,
                ),
                title="Cash First - Insufficient Advance",
            )


def get_customer_advance_amount(customer, company):
    ## Query GL Entry for customer's debit/credit balance
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

    ## Return advance if balance is negative (credit); else return 0
    return abs(flt(balance)) if flt(balance) < 0 else 0