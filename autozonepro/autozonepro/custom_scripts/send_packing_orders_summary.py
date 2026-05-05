import frappe
from frappe.utils import get_url


def send_packing_orders_summary():
    default_account = frappe.get_cached_value(
        "Email Account",
        {"default_outgoing": 1},
        ["email_id"],
        as_dict=True,
    )
    sender_email = default_account.email_id if default_account else None
    if not sender_email:
        frappe.log_error("No sender email configured.", "Packing Notification Failed")
        return

    recipient_emails = [
        # "manjot.riar@gmail.com",
        # "audit@autozonepro.org",
        # "davisorford5@gmail.com",
        "ernestben69@gmail.com"
    ]

    packing_orders = frappe.get_all(
        "Sales Order",
        filters=[
            ["workflow_state", "=", "Packing"],
            ["docstatus", "=", 1],
            ["status", "not in", ["Hold", "On Hold", "Closed"]],
        ],
        fields=["name", "customer", "owner", "modified"],
        order_by="modified desc",
    )

    site_url = get_url()
    rows_html = ""

    for order in packing_orders:
        days_pending = frappe.utils.date_diff(
            frappe.utils.nowdate(),
            order.modified.date() if hasattr(order.modified, "date") else order.modified,
        )
        creator_name = frappe.db.get_value("User", order.owner, "full_name") or order.owner
        order_link = f"{site_url}/app/sales-order/{order.name}"

        rows_html += f"""
        <tr>
            <td style="padding: 8px; border: 1px solid #ddd;">{order.name}</td>
            <td style="padding: 8px; border: 1px solid #ddd;">{order.customer}</td>
            <td style="padding: 8px; border: 1px solid #ddd;">{creator_name}</td>
            <td style="padding: 8px; border: 1px solid #ddd;">{days_pending} days</td>
            <td style="padding: 8px; border: 1px solid #ddd;">
                <a href="{order_link}" style="color: #0275d8; text-decoration: none;">View</a>
            </td>
        </tr>
        """

    if packing_orders:
        stage_html = f"""
            <p style="color:#b22222; font-weight: bold;">
                You have <strong>{len(packing_orders)} order(s)</strong> at Packing stage.
            </p>
        """
        table_html = f"""
            <p style="font-weight: bold; margin-top: 20px;">Packing Orders:</p>
            <table style="width: 100%; border-collapse: collapse; margin: 10px 0;">
                <thead>
                    <tr style="background-color: #f5f5f5;">
                        <th style="padding: 10px; border: 1px solid #ddd; text-align: left;">Order ID</th>
                        <th style="padding: 10px; border: 1px solid #ddd; text-align: left;">Customer</th>
                        <th style="padding: 10px; border: 1px solid #ddd; text-align: left;">Created By</th>
                        <th style="padding: 10px; border: 1px solid #ddd; text-align: left;">Days in Stage</th>
                        <th style="padding: 10px; border: 1px solid #ddd; text-align: center;">Action</th>
                    </tr>
                </thead>
                <tbody>
                    {rows_html}
                </tbody>
            </table>
        """
    else:
        stage_html = """
            <p style="color:#2e7d32; font-weight: bold;">
                No orders are currently at Packing stage.
            </p>
        """
        table_html = ""

    subject = f"EVENING SUMMARY: {len(packing_orders)} Order(s) at Packing Stage"

    for email in recipient_emails:
        message = f"""
        <html>
            <body style="font-family: Arial, sans-serif; line-height: 1.6;">
                <p>Good evening,</p>
                {stage_html}
                {table_html}
                <p style="margin-top: 20px; color:#666; font-size: 12px;">
                    This is an automated summary. Please review and take necessary action.
                </p>
                <br>
                <p>Best regards,<br><strong>Autozone Professional Limited</strong></p>
            </body>
        </html>
        """

        try:
            frappe.sendmail(
                recipients=[email],
                subject=subject,
                message=message,
                sender=sender_email,
                now=True,
            )
            frappe.logger().info(f"Packing summary sent to {email}")
        except Exception as e:
            frappe.log_error(
                f"Failed to send Packing summary to {email}: {str(e)}",
                "Packing Notification Error",
            )

    frappe.db.commit()
