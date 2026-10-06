import frappe
from frappe import _
from frappe.utils import cstr
from frappe.utils.data import get_link_to_form


restricted_reference_modes = {"bank", "mobile money"}


def validate(doc, method=None):
	validate_unique_reference_no_for_restricted_modes(doc)


def get_reference_digits(reference_no):
	return "".join(character for character in cstr(reference_no) if character.isascii() and character.isdigit())


def validate_unique_reference_no_for_restricted_modes(doc):
	mode_of_payment = cstr(doc.get("mode_of_payment")).strip().lower()
	reference_no = cstr(doc.get("reference_no")).strip()

	if mode_of_payment not in restricted_reference_modes or not reference_no:
		return

	doc.reference_no = reference_no
	reference_digits = get_reference_digits(reference_no)

	duplicate = frappe.db.multisql(
		{
			"mariadb": """
				select name, mode_of_payment, reference_no
				from `tabPayment Entry`
				where (
					trim(reference_no) = %s
					or (%s != '' and regexp_replace(reference_no, '[^0-9]', '') = %s)
				)
					and docstatus != 2
					and name != %s
				limit 1
			""",
			"postgres": """
				select name, mode_of_payment, reference_no
				from "tabPayment Entry"
				where (
					trim(reference_no) = %s
					or (%s != '' and regexp_replace(reference_no, '[^0-9]', '', 'g') = %s)
				)
					and docstatus != 2
					and name != %s
				limit 1
			""",
		},
		(reference_no, reference_digits, reference_digits, doc.name or ""),
		as_dict=True,
	)

	if duplicate:
		duplicate = duplicate[0]
		frappe.throw(
			_(
				"Reference No {0} has the same digits as Reference No {1}, already used in "
				"Payment Entry {2} for Mode of Payment {3}."
			).format(
				frappe.bold(reference_no),
				frappe.bold(duplicate.reference_no),
				get_link_to_form("Payment Entry", duplicate.name),
				frappe.bold(duplicate.mode_of_payment or _("Not Set")),
			),
			title=_("Duplicate Reference No"),
		)
