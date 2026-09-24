import json

import frappe
from frappe.utils import add_days, now_datetime
from frappe.utils.xlsxutils import make_xlsx


RECIPIENTS = ["manjot.riar@gmail.com"]


def send_price_changes():
    """Email an Excel report of Item Price rate changes from the last 24 hours."""
    rows = [
        [
            "Item Code",
            "Price List",
            "Old Rate",
            "New Rate",
            "Changed At",
            "Changed By",
        ]
    ]

    versions = frappe.get_all(
        "Version",
        filters={
            "ref_doctype": "Item Price",
            "creation": [">=", add_days(now_datetime(), -1)],
        },
        fields=["docname", "data", "creation", "owner"],
        order_by="creation asc",
    )

    for version in versions:
        try:
            data = json.loads(version.data or "{}")
        except (TypeError, json.JSONDecodeError):
            continue

        for change in data.get("changed", []):
            if len(change) < 3 or change[0] != "price_list_rate":
                continue

            item_price = frappe.db.get_value(
                "Item Price",
                version.docname,
                ["item_code", "price_list"],
                as_dict=True,
            )
            if not item_price:
                continue

            rows.append(
                [
                    item_price.item_code,
                    item_price.price_list,
                    change[1],
                    change[2],
                    version.creation,
                    version.owner,
                ]
            )

    if len(rows) == 1:
        return

    xlsx = make_xlsx(rows, "Price Changes")

    frappe.sendmail(
        recipients=RECIPIENTS,
        subject="Item price changes - last 24 hours",
        message="Attached are the items whose prices changed during the last 24 hours.",
        attachments=[
            {
                "fname": "price_changes.xlsx",
                "fcontent": xlsx.getvalue(),
            }
        ],
    )

