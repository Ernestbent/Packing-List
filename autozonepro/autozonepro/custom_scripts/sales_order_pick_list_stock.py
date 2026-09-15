import frappe
from frappe import _
from frappe.utils import cint, escape_html, flt


MAIN_LOCATION_WAREHOUSE = "Main Loc - APL"
CONTAINER_WAREHOUSES = (
    "Cont. No. 1 = MAEU-8382503 - APL",
    "Cont. No. 2 = FTBU-8875500 - APL",
)


def validate(doc, method=None):
    populate_container_quantities(doc)


def before_update_after_submit(doc, method=None):
    if doc.doctype != "Sales Order" or doc.docstatus != 1 or not doc.get("items"):
        return

    previous_doc = getattr(doc, "_doc_before_save", None)
    previous_state = previous_doc.workflow_state if previous_doc else None
    current_state = doc.workflow_state

    if current_state != "Picking" or previous_state == "Picking":
        return

    validate_create_pick_list_stock(doc)


def validate_create_pick_list_stock(doc):
    """Reject the workflow transition using current stock, before the state is saved."""
    required = {}
    for row in doc.items:
        if not row.item_code:
            continue
        # Bin quantities are in stock UOM, not necessarily the order's selling UOM.
        qty = flt(row.qty) * (flt(row.get("conversion_factor")) or 1)
        if row.item_code not in required:
            required[row.item_code] = {
                "item_code": row.item_code,
                "item_name": row.item_name or row.item_code,
                "required_qty": 0,
                "uom": row.get("stock_uom") or row.uom,
            }
        required[row.item_code]["required_qty"] += qty

    if not required:
        return

    stock_by_item = get_pick_list_stock_by_item(list(required))
    insufficient = []
    for item_code, item in required.items():
        stock = stock_by_item.get(item_code, {})
        main_qty = flt(stock.get("main_qty"))
        # Preserve the existing rule: this warning is for stock held in containers.
        if flt(stock.get("container_qty")) > 0 and item["required_qty"] > main_qty:
            insufficient.append({**item, **stock, "main_qty": main_qty})

    if insufficient:
        throw_stock_shortfall(insufficient, doc.company)


def throw_stock_shortfall(items, company):
    headings = [
        _("Item Code"), _("Item Name"), _("Required Qty (Stock UOM)"),
        _("Main Loc Qty"), _("Cont 1 (MAEU-8382503)"), _("Cont 2 (FTBU-8875500)"), _("UOM"),
    ]
    header = "".join("<th>{0}</th>".format(escape_html(label)) for label in headings)
    rows = []
    for item in items:
        values = [
            item["item_code"], item["item_name"], "{0:g}".format(item["required_qty"]),
            "{0:g}".format(item["main_qty"]), "{0:g}".format(item.get("container_1_qty", 0)),
            "{0:g}".format(item.get("container_2_qty", 0)), item["uom"],
        ]
        rows.append("<tr>{0}</tr>".format("".join("<td>{0}</td>".format(escape_html(value)) for value in values)))

    message = _(
        "Cannot complete <b>Create Pick List</b> because stock in the Main Location is less "
        "than the required quantity. The Sales Order has not moved to Picking."
    )
    message += "<p>{0}</p>".format(_(
        "Transfer stock from the containers to {0} using a Stock Entry, then try Create Pick List again."
    ).format(escape_html(MAIN_LOCATION_WAREHOUSE)))
    message += (
        '<div style="overflow-x:auto"><table class="table table-bordered">'
        '<thead><tr>{0}</tr></thead><tbody>{1}</tbody></table></div>'
    ).format(header, "".join(rows))

    frappe.throw(
        message,
        title=_("Stock Shortfall in Main Location"),
        wide=True,
        primary_action={
            "label": _("Make Stock Entry"),
            "client_action": "autozonepro.open_main_location_transfer",
            "args": {"company": company, "items": get_transfer_items(items)},
        },
    )


def get_transfer_items(items):
    """Prepare unsaved transfers in stock UOM, splitting between containers if needed."""
    transfers = []
    for item in items:
        remaining = item["required_qty"] - item["main_qty"]
        containers = sorted(
            zip(CONTAINER_WAREHOUSES, (flt(item.get("container_1_qty")), flt(item.get("container_2_qty")))),
            key=lambda entry: entry[1], reverse=True,
        )
        for warehouse, available in containers:
            qty = min(remaining, max(available, 0))
            if qty <= 0:
                continue
            transfers.append({
                "item_code": item["item_code"], "qty": qty, "uom": item["uom"],
                "stock_uom": item["uom"], "conversion_factor": 1,
                "s_warehouse": warehouse, "t_warehouse": MAIN_LOCATION_WAREHOUSE,
            })
            remaining -= qty
    return transfers


def get_pick_list_stock_by_item(item_codes):
    if not item_codes:
        return {}

    rows = frappe.db.sql(
        """
        select
            item_code,
            sum(case when warehouse = %(main_warehouse)s then actual_qty else 0 end) as main_qty,
            sum(case when warehouse in %(container_warehouses)s then actual_qty else 0 end) as container_qty,
            sum(case when warehouse = %(container_1)s then actual_qty else 0 end) as container_1_qty,
            sum(case when warehouse = %(container_2)s then actual_qty else 0 end) as container_2_qty
        from `tabBin`
        where item_code in %(item_codes)s
          and warehouse in %(warehouses)s
        group by item_code
        """,
        {
            "item_codes": tuple(item_codes),
            "main_warehouse": MAIN_LOCATION_WAREHOUSE,
            "container_warehouses": CONTAINER_WAREHOUSES,
            "container_1": CONTAINER_WAREHOUSES[0],
            "container_2": CONTAINER_WAREHOUSES[1],
            "warehouses": (MAIN_LOCATION_WAREHOUSE, *CONTAINER_WAREHOUSES),
        },
        as_dict=True,
    )

    return {
        row.item_code: {
            "main_qty": flt(row.main_qty),
            "container_qty": flt(row.container_qty),
            "container_1_qty": flt(row.container_1_qty),
            "container_2_qty": flt(row.container_2_qty),
        }
        for row in rows
    }


def populate_container_quantities(doc):
    if doc.doctype != "Sales Order" or not doc.get("items"):
        return

    item_codes = [row.item_code for row in doc.items if row.item_code]
    if not item_codes:
        return

    stock_by_item = get_pick_list_stock_by_item(item_codes)

    for row in doc.items:
        if not row.item_code:
            row.containers = 0
            continue

        stock = stock_by_item.get(row.item_code, {})
        row.containers = cint(flt(stock.get("container_qty")))
