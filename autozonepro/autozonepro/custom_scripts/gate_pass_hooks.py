import frappe
from frappe import _
from frappe.model.workflow import apply_workflow, get_transitions


def on_submit(doc, method):
    sales_orders = []

    for row in doc.get("table_zcvy") or []:
        sales_order = (row.get("sales_order") or "").strip()
        if sales_order and sales_order not in sales_orders:
            sales_orders.append(sales_order)

    if not sales_orders:
        return

    sales_order_meta = frappe.get_meta("Sales Order")
    has_gate_pass_field = sales_order_meta.has_field("gate_pass")

    for sales_order_name in sales_orders:
        so = frappe.get_doc("Sales Order", sales_order_name)

        if has_gate_pass_field and so.get("gate_pass") != doc.name:
            frappe.db.set_value(
                "Sales Order",
                sales_order_name,
                "gate_pass",
                doc.name,
                update_modified=False,
            )
            so.gate_pass = doc.name

        if so.workflow_state == "In Transit":
            continue

        available_actions = [
            transition.get("action")
            for transition in get_transitions(so)
        ]

        if "Start Transit" not in available_actions:
            frappe.throw(
                _(
                    "Sales Order {0} is in workflow state {1}. The workflow action Start Transit is not available from this state."
                ).format(frappe.bold(sales_order_name), frappe.bold(so.workflow_state or _("Not Set"))),
                title=_("Invalid Sales Order State"),
            )

        try:
            apply_workflow(so, "Start Transit")
        except Exception:
            frappe.log_error(
                frappe.get_traceback(),
                _("Failed to move Sales Order {0} to In Transit from Gate Pass {1}").format(
                    sales_order_name, doc.name
                ),
            )
            raise
