import json

import frappe
from frappe.desk.form import linked_with


def _as_list(value):
    if not value:
        return []
    if isinstance(value, str):
        value = json.loads(value)
    return list(value)


def _ignored_doctypes(value=None):
    ignored = _as_list(value)
    if "Gate Pass" not in ignored:
        ignored.append("Gate Pass")
    return ignored


def _unique_documents(documents):
    unique = []
    seen = set()

    for document in documents:
        key = (document.get("doctype"), document.get("name"))
        if key in seen:
            continue
        seen.add(key)
        unique.append(document)

    return unique


@frappe.whitelist()
def get_submitted_linked_docs(doctype, name, ignore_doctypes_on_cancel_all=None):
    result = linked_with.get_submitted_linked_docs(
        doctype,
        name,
        _ignored_doctypes(ignore_doctypes_on_cancel_all),
    )
    documents = _unique_documents(result.get("docs") or [])
    return {"docs": documents, "count": len(documents)}


@frappe.whitelist()
def cancel_all_linked_docs(docs, ignore_doctypes_on_cancel_all=None):
    documents = _unique_documents(_as_list(docs))
    return linked_with.cancel_all_linked_docs(
        json.dumps(documents),
        _ignored_doctypes(ignore_doctypes_on_cancel_all),
    )
