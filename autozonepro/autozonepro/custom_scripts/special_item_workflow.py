import frappe


SPECIAL_ITEM_CONDITION = "doc['items'] and doc['items'][0]['item_code'] == 'CE300176PR'"
NORMAL_ITEM_CONDITION = "not (doc['items'] and doc['items'][0]['item_code'] == 'CE300176PR')"
START_BILLING_ACTION = "Start Billing"


def configure_special_item_workflow():
	"""Apply the tyre shortcut to the currently active Sales Order workflow."""
	workflow_name = frappe.db.get_value(
		"Workflow",
		{"document_type": "Sales Order", "is_active": 1},
		"name",
	)
	if not workflow_name:
		return

	if not frappe.db.exists("Workflow Action Master", START_BILLING_ACTION):
		frappe.get_doc(
			{
				"doctype": "Workflow Action Master",
				"workflow_action_name": START_BILLING_ACTION,
			}
		).insert(ignore_permissions=True)

	workflow = frappe.get_doc("Workflow", workflow_name)
	changed = False

	for transition in workflow.transitions:
		if transition.state == "Approved" and transition.action == "Create Pick List":
			if transition.condition != NORMAL_ITEM_CONDITION:
				transition.condition = NORMAL_ITEM_CONDITION
				changed = True

	tire_transition = next(
		(
			transition
			for transition in workflow.transitions
			if transition.state == "Approved"
			and transition.action == START_BILLING_ACTION
			and transition.next_state == "Billing"
		),
		None,
	)

	if tire_transition:
		expected_values = {
			"allowed": "Billing",
			"condition": SPECIAL_ITEM_CONDITION,
			"allow_self_approval": 1,
		}
		for fieldname, value in expected_values.items():
			if tire_transition.get(fieldname) != value:
				tire_transition.set(fieldname, value)
				changed = True
	else:
		workflow.append(
			"transitions",
			{
				"state": "Approved",
				"action": START_BILLING_ACTION,
				"next_state": "Billing",
				"allowed": "Billing",
				"allow_self_approval": 1,
				"condition": SPECIAL_ITEM_CONDITION,
			},
		)
		changed = True

	if changed:
		workflow.save(ignore_permissions=True)
		frappe.clear_cache(doctype="Sales Order")
