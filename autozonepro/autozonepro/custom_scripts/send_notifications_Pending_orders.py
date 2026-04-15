## Morning Notification: Pending Credit Approval Orders
## Schedule: 7:00 AM daily

import frappe
from frappe.utils import get_url

def send_morning_pending_credit_notifications():
    ## Get default sender email
    sender_email = frappe.db.get_value("Email Account", {"default_outgoing": 1}, "email_id")
    if not sender_email:
        frappe.log_error("No sender email configured.", "Morning Notification Failed")
        return
    
    ## Define fixed recipient emails
    recipient_emails = [
        "manjot.riar@gmail.com",
        "audit@autozonepro.org",
        "davisorford5@gmail.com",
        "ernestben69@gmail.com"
    ]
    
    ## Get all orders in Pending Credit Approval state
    pending_orders = frappe.get_all(
        "Sales Order",
        filters=[
            ["workflow_state", "=", "Pending Credit Approval"],
            ["docstatus", "=", 1],
            ["status", "not in", ["Hold", "On Hold", "Closed"]]
        ],
        fields=["name", "transaction_date", "customer", "owner", "modified"],
        order_by="modified desc"
    )
    
    if not pending_orders:
        frappe.logger().info("No orders pending credit approval for morning notification")
        return
    
    ## Build order summary
    order_list_html = ""
    for order in pending_orders:
        days_pending = frappe.utils.date_diff(frappe.utils.nowdate(), order.modified.date() if hasattr(order.modified, 'date') else order.modified)
        creator_name = frappe.db.get_value("User", order.owner, "full_name") or order.owner
        site_url = get_url()
        order_link = f"{site_url}/app/sales-order/{order.name}"
        
        order_list_html += f"""
        <tr>
            <td style="padding: 8px; border: 1px solid #ddd;">{order.name}</td>
            <td style="padding: 8px; border: 1px solid #ddd;">{order.customer}</td>
            <td style="padding: 8px; border: 1px solid #ddd;">{creator_name}</td>
            <td style="padding: 8px; border: 1px solid #ddd;">{days_pending} days</td>
            <td style="padding: 8px; border: 1px solid #ddd;">
                <a href="{order_link}" style="color: #d9534f; text-decoration: none;">Review</a>
            </td>
        </tr>
        """
    
    ## Send email to each recipient
    subject = f"MORNING ALERT: {len(pending_orders)} Order(s) Awaiting Credit Approval"
    
    for email in recipient_emails:
        message = f"""
        <html>
            <body style="font-family: Arial, sans-serif; line-height: 1.6;">
                <p>Good morning,</p>
                <p style="color:#b22222; font-weight: bold;">
                    You have <strong>{len(pending_orders)} order(s)</strong> awaiting credit approval.
                </p>
                
                <table style="width: 100%; border-collapse: collapse; margin: 20px 0;">
                    <thead>
                        <tr style="background-color: #f5f5f5;">
                            <th style="padding: 10px; border: 1px solid #ddd; text-align: left;">Order ID</th>
                            <th style="padding: 10px; border: 1px solid #ddd; text-align: left;">Customer</th>
                            <th style="padding: 10px; border: 1px solid #ddd; text-align: left;">Created By</th>
                            <th style="padding: 10px; border: 1px solid #ddd; text-align: left;">Days Pending</th>
                            <th style="padding: 10px; border: 1px solid #ddd; text-align: center;">Action</th>
                        </tr>
                    </thead>
                    <tbody>
                        {order_list_html}
                    </tbody>
                </table>
                
                <p style="color:#ff6600;">Please prioritize orders pending for 2+ days.</p>
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
                now=True
            )
            frappe.logger().info(f"Morning notification sent to {email}")
        except Exception as e:
            frappe.log_error(
                f"Failed to send morning notification to {email}: {str(e)}",
                "Morning Notification Error"
            )
    
    frappe.db.commit()
