# gate_pass.py
# Server-side enforcement of Gate Pass requirement before In Transit

import frappe
from frappe import _
from frappe.utils import today

def validate_gate_pass_before_transit(doc, method, workflow_action=None):

    ## Only enforce on Start Transit action
    if workflow_action != "Start Transit":
        return

    ## Check gate pass field is filled
    if not doc.gate_pass:
        frappe.throw(
            _("Sales Order {0} has no linked Gate Pass. Cannot move to 'In Transit'.").format(
                frappe.bold(doc.name)
            ),
            title=_("Gate Pass Required")
        )

    ## Fetch the linked gate pass
    gp = frappe.get_doc("Gate Pass", doc.gate_pass)

    ## Check gate pass is submitted
    if gp.docstatus != 1:
        frappe.throw(
            _("Gate Pass {0} is not submitted yet.").format(
                frappe.bold(doc.gate_pass)
            ),
            title=_("Gate Pass Not Submitted")
        )

    ## Check gate pass date matches today
    if str(gp.date) != today():
        frappe.throw(
            _("Gate Pass {0} is dated {1}, not today ({2}).").format(
                frappe.bold(doc.gate_pass),
                gp.date,
                today()
            ),
            title=_("Gate Pass Date Mismatch")
        )