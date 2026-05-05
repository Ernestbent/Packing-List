## Notification: Billed Orders Summary

import frappe
from frappe.utils import get_url


def send_billed_orders_notifications():
    ## Get default sender email
    sender_email = frappe.db.get_value("Email Account", {"default_outgoing": 1}, "email_id")
    if not sender_email:
        frappe.log_error("No sender email configured.", "Billed Notification Failed")
        return

    ## Define fixed recipient emails
    recipient_emails = [
        "manjot.riar@gmail.com",
        "audit@autozonepro.org",
        "davisorford5@gmail.com",
        "ernestben69@gmail.com",
    ]

    stage_name = "Billed"
    stage_orders = frappe.get_all(
        "Sales Order",
        filters=[
            ["workflow_state", "=", stage_name],
            ["docstatus", "=", 1],
            ["status", "not in", ["Hold", "On Hold", "Closed"]],
        ],
        fields=["name", "customer", "owner", "modified"],
        order_by="modified desc",
    )

    stage_table_html = ""
    site_url = get_url()

    if stage_orders:
        rows_html = ""
        for order in stage_orders:
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

        stage_table_html = f"""
            <p style="font-weight: bold; margin-top: 20px;">{stage_name} Orders ({len(stage_orders)})</p>
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
        stage_table_html = f"""
            <p style="font-weight: bold; margin-top: 20px;">{stage_name} Orders (0)</p>
            <p style="color:#2e7d32; margin: 6px 0 0;">No orders currently in {stage_name.lower()} stage.</p>
        """

    ## Send email to each recipient
    subject = f"EVENING SUMMARY: {len(stage_orders)} Order(s) at Billed Stage"

    for email in recipient_emails:
        message = f"""
        <html>
            <body style="font-family: Arial, sans-serif; line-height: 1.6;">
                <p>Good evening,</p>
                <p style="color:#333;">
                    End-of-day summary: <strong>{len(stage_orders)} order(s)</strong> currently in Billed stage.
                </p>
                {stage_table_html}

                <p style="margin-top: 20px; color:#666; font-size: 12px;">
                    This is an automated daily summary. Please review  orders and take necessary action.
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
            frappe.logger().info(f"Billed notification sent to {email}")
        except Exception as e:
            frappe.log_error(
                f"Failed to send Billed notification to {email}: {str(e)}",
                "Billed Notification Error",
            )

    frappe.db.commit()
