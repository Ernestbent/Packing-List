import re

import frappe
import requests
from frappe import _
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.utils import escape_html, get_url, now_datetime
from frappe.utils.synchronization import filelock


SPECIAL_ITEM_CODE = "CE300176PR"
TEMPLATE_NAME = "remote_shipment"
TEMPLATE_LANGUAGE = "en"

# Delivery Notes and their handover links go to the remote packing team.
DELIVERY_NOTE_RECIPIENTS = (
	{"name": "Mark", "phone": "0757001909"},
	{"name": "Bridget", "phone": "+256 708 390020"},
	{"name": "Justine", "phone": "+256 752 374696"},
)
DELIVERY_NOTE_EMAIL_RECIPIENTS = (
	{"name": "Mark", "email": "othienobenedict8@gmail.com"},
	{"name": "Shamba Sales 1", "email": "Sales.shamba1@onestopautoco.com"},
	{"name": "Shamba Sales 2", "email": "Sales.shamba2@onestopautoco.com"},
	{"name": "Service Team", "email": "Service@onestopautoco.com"},
)

STATUS_FIELD = "custom_remote_shipment_whatsapp_status"
MESSAGE_ID_FIELD = "custom_remote_shipment_whatsapp_message_id"
EMAIL_STATUS_FIELD = "custom_remote_shipment_email_status"


def setup_custom_fields():
	"""Create internal fields used to prevent duplicate WhatsApp sends."""
	tracking_fields = [
		{
			"fieldname": STATUS_FIELD,
			"label": "Remote Shipment WhatsApp Status",
			"fieldtype": "Select",
			"options": "Not Sent\nQueued\nSent\nFailed",
			"default": "Not Sent",
			"insert_after": "status",
			"hidden": 1,
			"read_only": 1,
			"allow_on_submit": 1,
			"no_copy": 1,
		},
		{
			"fieldname": MESSAGE_ID_FIELD,
			"label": "Remote Shipment WhatsApp Message ID",
			"fieldtype": "Data",
			"insert_after": STATUS_FIELD,
			"hidden": 1,
			"read_only": 1,
			"allow_on_submit": 1,
			"no_copy": 1,
		},
		{
			"fieldname": EMAIL_STATUS_FIELD,
			"label": "Remote Shipment Email Status",
			"fieldtype": "Select",
			"options": "Not Sent\nQueued\nSent\nFailed",
			"default": "Not Sent",
			"insert_after": MESSAGE_ID_FIELD,
			"hidden": 1,
			"read_only": 1,
			"allow_on_submit": 1,
			"no_copy": 1,
		},
	]
	create_custom_fields(
		{
			"Delivery Note": [field.copy() for field in tracking_fields],
		},
		update=True,
	)


def queue_remote_shipment_notification(doc, method=None):
	"""Queue one message after a special-item Delivery Note is submitted."""
	if isinstance(doc, str):
		doc = frappe.get_doc("Delivery Note", doc)
	if doc.docstatus != 1 or not _is_remote_shipment(doc):
		return

	status = doc.get(STATUS_FIELD) or "Not Sent"
	if status in {"Queued", "Sent"}:
		return

	doc.db_set(STATUS_FIELD, "Queued", update_modified=False)
	frappe.enqueue(
		"autozonepro.autozonepro.custom_scripts.remote_shipment_whatsapp.send_remote_shipment_notification",
		queue="long",
		timeout=300,
		enqueue_after_commit=True,
		job_id=f"remote-shipment-whatsapp-{doc.name}",
		deduplicate=True,
		delivery_note_name=doc.name,
	)


def queue_remote_shipment_email(doc, method=None):
	"""Queue the Delivery Note PDF and handover link for email recipients."""
	if isinstance(doc, str):
		doc = frappe.get_doc("Delivery Note", doc)
	if doc.docstatus != 1 or not _is_remote_shipment(doc):
		return

	status = doc.get(EMAIL_STATUS_FIELD) or "Not Sent"
	if status in {"Queued", "Sent"}:
		return

	doc.db_set(EMAIL_STATUS_FIELD, "Queued", update_modified=False)
	frappe.enqueue(
		"autozonepro.autozonepro.custom_scripts.remote_shipment_whatsapp.send_remote_shipment_email",
		queue="long",
		timeout=300,
		enqueue_after_commit=True,
		job_id=f"remote-shipment-email-{doc.name}",
		deduplicate=True,
		delivery_note_name=doc.name,
	)


def send_remote_shipment_notification(delivery_note_name):
	"""Upload the Delivery Note PDF and send the approved Meta template."""
	lock_name = f"remote-shipment-whatsapp-{frappe.scrub(delivery_note_name)}"
	with filelock(lock_name, timeout=10):
		delivery_note = frappe.get_doc("Delivery Note", delivery_note_name)
		if delivery_note.get(STATUS_FIELD) == "Sent":
			return

		try:
			_validate_delivery_note(delivery_note)
			pdf_content = frappe.get_print("Delivery Note", delivery_note.name, as_pdf=True)
			file_doc = _get_or_create_pdf_file(delivery_note, pdf_content)
			settings = frappe.get_single("Whatsapp Setting")
			access_token = _get_access_token(settings)
			phone_number_id = settings.get("phone_number_id")
			if not access_token or not phone_number_id:
				frappe.throw(_("WhatsApp access token and phone number ID must be configured."))

			api_version = _get_api_version(settings.get("app_version"))
			message_ids = []
			for recipient in DELIVERY_NOTE_RECIPIENTS:
				phone = _normalize_ugandan_phone(recipient["phone"])
				media_id = _upload_document(
					pdf_content,
					file_doc.file_name,
					access_token,
					phone_number_id,
					api_version,
				)
				message_id = _send_template(
					phone=phone,
					recipient_name=recipient["name"],
					sales_order=sales_order,
					delivery_note=delivery_note.name,
					media_id=media_id,
					file_name=file_doc.file_name,
					access_token=access_token,
					phone_number_id=phone_number_id,
					api_version=api_version,
				)
				message_ids.append(message_id)
				_log_outgoing_message(
					phone=phone,
					recipient_name=recipient["name"],
					sales_order=sales_order,
					delivery_note=delivery_note,
					file_doc=file_doc,
					media_id=media_id,
					message_id=message_id,
				)

			# Commit immediately after the external send so a later worker error cannot
			# cause a duplicate message on retry.
			frappe.db.set_value(
				"Delivery Note",
				delivery_note.name,
				{
					STATUS_FIELD: "Sent",
					MESSAGE_ID_FIELD: ", ".join(message_ids),
				},
				update_modified=False,
			)
			frappe.db.commit()
		except Exception:
			frappe.db.rollback()
			frappe.db.set_value(
				"Delivery Note",
				delivery_note.name,
				STATUS_FIELD,
				"Failed",
				update_modified=False,
			)
			frappe.db.commit()
			frappe.log_error(
				title=f"Remote Shipment WhatsApp failed: {delivery_note.name}",
				message=frappe.get_traceback(),
			)
			raise


def send_remote_shipment_email(delivery_note_name):
	"""Email the submitted Delivery Note without depending on WhatsApp."""
	lock_name = f"remote-shipment-email-{frappe.scrub(delivery_note_name)}"
	with filelock(lock_name, timeout=10):
		delivery_note = frappe.get_doc("Delivery Note", delivery_note_name)
		if delivery_note.get(EMAIL_STATUS_FIELD) == "Sent":
			return

		try:
			_validate_delivery_note(delivery_note)
			sales_order = _get_sales_order(delivery_note)
			pdf_content = frappe.get_print("Delivery Note", delivery_note.name, as_pdf=True)
			file_doc = _get_or_create_pdf_file(delivery_note, pdf_content)
			handover_url = get_url(
				f"/third-party-shipment/new?delivery_note={delivery_note.name}"
			)

			for recipient in DELIVERY_NOTE_EMAIL_RECIPIENTS:
				message = _build_delivery_note_email(
					recipient_name=recipient["name"],
					handover_url=handover_url,
				)
				frappe.sendmail(
					recipients=[recipient["email"]],
					subject=_("Delivery Note {0} - Handover Required").format(
						delivery_note.name
					),
					message=message,
					attachments=[
						{"fname": file_doc.file_name, "fcontent": pdf_content}
					],
					reference_doctype="Delivery Note",
					reference_name=delivery_note.name,
					add_unsubscribe_link=0,
					now=True,
				)

			frappe.db.set_value(
				"Delivery Note",
				delivery_note.name,
				EMAIL_STATUS_FIELD,
				"Sent",
				update_modified=False,
			)
			frappe.db.commit()
		except Exception:
			frappe.db.rollback()
			frappe.db.set_value(
				"Delivery Note",
				delivery_note.name,
				EMAIL_STATUS_FIELD,
				"Failed",
				update_modified=False,
			)
			frappe.db.commit()
			frappe.log_error(
				title=f"Remote Shipment Email failed: {delivery_note.name}",
				message=frappe.get_traceback(),
			)
			raise


def _build_delivery_note_email(*, recipient_name, handover_url):
	return f"""
		<p>Hello {escape_html(recipient_name)},</p>
		<p>A new tyre shipment is ready for handover.</p>
		<p>Please enter the final driver and transport details using the link below:</p>
		<p><a href="{escape_html(handover_url)}">Enter Courier Details</a></p>
		<p>The submitted Delivery Note PDF is attached.</p>
		<p>Regards,<br><strong>Autozone Professional Limited</strong></p>
	"""
def _is_remote_shipment(delivery_note):
	items = delivery_note.get("items") or []
	return bool(items) and all(row.item_code == SPECIAL_ITEM_CODE for row in items)


def _validate_delivery_note(delivery_note):
	if delivery_note.docstatus != 1:
		frappe.throw(_("Delivery Note {0} must be submitted.").format(delivery_note.name))
	if not _is_remote_shipment(delivery_note):
		frappe.throw(
			_("Delivery Note {0} is not a {1} remote shipment.").format(
				delivery_note.name, SPECIAL_ITEM_CODE
			)
		)
def _get_sales_order(delivery_note):
	sales_orders = sorted(
		{row.against_sales_order for row in delivery_note.items if row.against_sales_order}
	)
	if not sales_orders:
		frappe.throw(
			_("Delivery Note {0} is not linked to a Sales Order.").format(delivery_note.name)
		)
	if len(sales_orders) != 1:
		frappe.throw(
			_("Delivery Note {0} is linked to more than one Sales Order.").format(
				delivery_note.name
			)
		)
	return sales_orders[0]


def _get_access_token(settings):
	try:
		return settings.get_password("access_token") or settings.get("access_token")
	except Exception:
		return settings.get("access_token")


def _get_api_version(value):
	version = (value or "").strip()
	if re.fullmatch(r"v?\d+\.\d+", version):
		return version if version.startswith("v") else f"v{version}"
	return "v24.0"


def _normalize_ugandan_phone(value):
	phone = re.sub(r"\D", "", value or "")
	if phone.startswith("256"):
		return phone
	if phone.startswith("0"):
		return f"256{phone[1:]}"
	if len(phone) == 9:
		return f"256{phone}"
	frappe.throw(_("Invalid WhatsApp telephone number: {0}").format(value))


def _get_or_create_document_file(document, pdf_content):
	file_name = f"{document.doctype} {document.name}.pdf"
	existing_name = frappe.db.get_value(
		"File",
		{
			"attached_to_doctype": document.doctype,
			"attached_to_name": document.name,
			"file_name": file_name,
		},
		"name",
	)
	if existing_name:
		return frappe.get_doc("File", existing_name)

	return frappe.get_doc(
		{
			"doctype": "File",
			"file_name": file_name,
			"is_private": 1,
			"content": pdf_content,
			"attached_to_doctype": document.doctype,
			"attached_to_name": document.name,
		}
	).insert(ignore_permissions=True)


def _get_or_create_pdf_file(delivery_note, pdf_content):
	return _get_or_create_document_file(delivery_note, pdf_content)


def _upload_document(
	pdf_content,
	file_name,
	access_token,
	phone_number_id,
	api_version,
	document_label=_("Delivery Note"),
):
	try:
		response = requests.post(
			f"https://graph.facebook.com/{api_version}/{phone_number_id}/media",
			headers={"Authorization": f"Bearer {access_token}"},
			data={"messaging_product": "whatsapp", "type": "application/pdf"},
			files={"file": (file_name, pdf_content, "application/pdf")},
			timeout=60,
		)
	except requests.RequestException as error:
		# Media upload is safe to repeat because no recipient message has been sent yet.
		raise frappe.RetryBackgroundJobError(
			_("Temporary WhatsApp media-upload failure: {0}").format(str(error))
		) from error
	result = _response_json(response)
	if response.status_code == 429 or response.status_code >= 500:
		raise frappe.RetryBackgroundJobError(
			_("Temporary WhatsApp media-upload failure: {0}").format(
				_safe_api_error(result, response.status_code)
			)
		)
	if not response.ok or not result.get("id"):
		raise frappe.ValidationError(
			_("WhatsApp could not upload the {0} PDF: {1}").format(
				document_label,
				_safe_api_error(result, response.status_code)
			)
		)
	return result["id"]


def _send_template(
	*,
	phone,
	recipient_name,
	sales_order,
	delivery_note,
	media_id,
	file_name,
	access_token,
	phone_number_id,
	api_version,
):
	payload = build_template_payload(
		phone=phone,
		recipient_name=recipient_name,
		sales_order=sales_order,
		delivery_note=delivery_note,
		media_id=media_id,
		file_name=file_name,
	)
	response = requests.post(
		f"https://graph.facebook.com/{api_version}/{phone_number_id}/messages",
		headers={
			"Authorization": f"Bearer {access_token}",
			"Content-Type": "application/json",
		},
		json=payload,
		timeout=30,
	)
	result = _response_json(response)
	messages = result.get("messages") or []
	if not response.ok or not messages or not messages[0].get("id"):
		raise frappe.ValidationError(
			_("WhatsApp rejected the remote shipment message: {0}").format(
				_safe_api_error(result, response.status_code)
			)
		)
	return messages[0]["id"]


def build_template_payload(
	*, phone, recipient_name, sales_order, delivery_note, media_id, file_name
):
	"""Build the positional template payload. Kept separate for safe testing."""
	return {
		"messaging_product": "whatsapp",
		"to": phone,
		"type": "template",
		"template": {
			"name": TEMPLATE_NAME,
			"language": {"code": TEMPLATE_LANGUAGE},
			"components": [
				{
					"type": "header",
					"parameters": [
						{
							"type": "document",
							"document": {"id": media_id, "filename": file_name},
						}
					],
				},
				{
					"type": "body",
					"parameters": [
						{"type": "text", "text": recipient_name},
						{"type": "text", "text": sales_order},
					],
				},
				{
					"type": "button",
					"sub_type": "url",
					"index": "0",
					"parameters": [{"type": "text", "text": delivery_note}],
				},
			],
		},
	}


def _response_json(response):
	try:
		return response.json()
	except ValueError:
		return {"error": {"message": response.text[:500]}}


def _safe_api_error(result, status_code):
	error = result.get("error") or {}
	message = error.get("message") if isinstance(error, dict) else str(error)
	return message or _("HTTP status {0}").format(status_code)


def _log_outgoing_message(
	*, phone, recipient_name, sales_order, delivery_note, file_doc, media_id, message_id
):
	if not frappe.db.exists("DocType", "Whatsapp Message"):
		return

	message = (
		f"Hello {recipient_name},\n\n"
		f"Please find attached the Delivery Note for Sales Order *{sales_order}*.\n\n"
		f"*Item:* {SPECIAL_ITEM_CODE}\n\n"
		"Please click the button below to enter the driver and transport details."
	)
	values = {
		"doctype": "Whatsapp Message",
		"from_number": phone,
		"message_type": "template",
		"message": message,
		"message_status": "sent",
		"media_id": media_id,
		"message_id": message_id,
		"timestamp": now_datetime().strftime("%H:%M:%S"),
		"customer": delivery_note.customer,
	}
	meta = frappe.get_meta("Whatsapp Message")
	optional_values = {
		"custom_status": "Outgoing",
		"custom_document": file_doc.file_url,
		"custom_template_header_type": "Document",
		"custom_template_header_file": file_doc.file_url,
	}
	for fieldname, value in optional_values.items():
		if meta.has_field(fieldname):
			values[fieldname] = value

	try:
		frappe.get_doc(values).insert(ignore_permissions=True)
	except Exception:
		# The message has already been accepted by Meta. A local audit-log error
		# must not mark it failed and trigger a duplicate send.
		frappe.log_error(
			title=f"Remote Shipment WhatsApp log failed: {delivery_note.name}",
			message=frappe.get_traceback(),
		)
