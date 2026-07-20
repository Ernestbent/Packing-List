import frappe
from frappe import _
from frappe.utils import cint, flt


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

    item_codes = [row.item_code for row in doc.items if row.item_code]
    if not item_codes:
        return

    stock_by_item = get_pick_list_stock_by_item(item_codes)
    insufficient_rows = []

    for row in doc.items:
        if not row.item_code:
            continue

        stock = stock_by_item.get(row.item_code, {})
        main_qty = flt(stock.get("main_qty"))
        container_qty = flt(stock.get("container_qty"))
        ordered_qty = flt(row.qty)

        if container_qty > 0 and ordered_qty > main_qty:
            insufficient_rows.append(
                {
                    "item_code": row.item_code,
                    "item_name": row.item_name,
                    "ordered_qty": ordered_qty,
                    "main_qty": main_qty,
                    "container_qty": container_qty,
                    "uom": row.uom,
                }
            )

    if not insufficient_rows:
        return

    item_lines = "".join(
        "<li>{item_code} ({item_name}) - Ordered: <b>{ordered_qty:g}</b>, Main Location: "
        "<b>{main_qty:g}</b>, Containers: <b>{container_qty:g}</b> {uom}</li>".format(
            item_code=frappe.bold(row["item_code"]),
            item_name=frappe.utils.escape_html(row["item_name"] or ""),
            ordered_qty=row["ordered_qty"],
            main_qty=row["main_qty"],
            container_qty=row["container_qty"],
            uom=frappe.utils.escape_html(row["uom"] or ""),
        )
        for row in insufficient_rows
    )

    frappe.throw(
        _(
            "Cannot move this Sales Order to <b>Picking</b> because Main Location stock is short "
            "for the items below, even though stock exists in the containers."
            "<br><br><ul>{0}</ul>"
            "<br>Transfer stock from the containers to <b>{1}</b> before creating the Pick List."
        ).format(item_lines, frappe.bold(MAIN_LOCATION_WAREHOUSE)),
        title=_("Stock Shortfall In Main Location"),
    )


def get_pick_list_stock_by_item(item_codes):
    rows = frappe.db.sql(
        """
        select
            item_code,
            sum(case when warehouse = %(main_warehouse)s then actual_qty else 0 end) as main_qty,
            sum(case when warehouse in %(container_warehouses)s then actual_qty else 0 end) as container_qty
        from `tabBin`
        where item_code in %(item_codes)s
          and warehouse in %(warehouses)s
        group by item_code
        """,
        {
            "item_codes": tuple(item_codes),
            "main_warehouse": MAIN_LOCATION_WAREHOUSE,
            "container_warehouses": CONTAINER_WAREHOUSES,
            "warehouses": (MAIN_LOCATION_WAREHOUSE, *CONTAINER_WAREHOUSES),
        },
        as_dict=True,
    )

    return {
        row.item_code: {
            "main_qty": flt(row.main_qty),
            "container_qty": flt(row.container_qty),
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
