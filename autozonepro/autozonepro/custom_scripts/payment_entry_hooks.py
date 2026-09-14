import frappe
from frappe import _
from frappe.utils import cstr
from frappe.utils.data import get_link_to_form


restricted_reference_modes = {"bank", "mobile money"}


def validate(doc, method=None):
	validate_unique_reference_no_for_restricted_modes(doc)


def validate_unique_reference_no_for_restricted_modes(doc):
	mode_of_payment = cstr(doc.get("mode_of_payment")).strip().lower()
	reference_no = cstr(doc.get("reference_no")).strip()

	if mode_of_payment not in restricted_reference_modes or not reference_no:
		return

	doc.reference_no = reference_no

	duplicate = frappe.db.sql(
		"""
		select name, mode_of_payment
		from `tabPayment Entry`
		where trim(reference_no) = %s
			and lower(trim(mode_of_payment)) in ('bank', 'mobile money')
			and docstatus != 2
			and name != %s
		limit 1
		""",
		(reference_no, doc.name or ""),
		as_dict=True,
	)

	if duplicate:
		duplicate = duplicate[0]
		frappe.throw(
			_(
				"Reference No {0} is already used in Payment Entry {1} for Mode of Payment {2}."
			).format(
				frappe.bold(reference_no),
				get_link_to_form("Payment Entry", duplicate.name),
				frappe.bold(duplicate.mode_of_payment),
			),
			title=_("Duplicate Reference No"),
		)
