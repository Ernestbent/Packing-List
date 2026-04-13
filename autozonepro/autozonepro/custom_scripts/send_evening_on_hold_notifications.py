## Evening Notification: On Hold Orders Summary
## Schedule: 6:00 PM daily

import frappe
from frappe.utils import get_url

def send_evening_on_hold_notifications():
    ## Get default sender email
    sender_email = frappe.db.get_value("Email Account", {"default_outgoing": 1}, "email_id")
    if not sender_email:
        frappe.log_error("No sender email configured.", "Evening On Hold Notification Failed")
        return
    
    ## Define fixed recipient emails
    recipient_emails = [
        "manjot.riar@gmail.com",
        "audit@autozonepro.org",
        "davisorford5@gmail.com"
    ]
    
    ## Get all orders in On Hold state
    on_hold_orders = frappe.get_all(
        "Sales Order",
        filters={
            "workflow_state": "On Hold",
            "docstatus": 1
        },
        fields=["name", "transaction_date", "customer", "owner", "workflow_state", "modified"],
        order_by="modified desc"
    )
    
    if not on_hold_orders:
        frappe.logger().info("No on hold orders for evening notification")
        return
    
    ## Build detailed order list
    order_list_html = ""
    for order in on_hold_orders:
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
                <a href="{order_link}" style="color: #0275d8; text-decoration: none;">View</a>
            </td>
        </tr>
        """
    
    ## Send email to each recipient
    subject = f"EVENING SUMMARY: {len(on_hold_orders)} Order(s) On Hold"
    
    for email in recipient_emails:
        message = f"""
        <html>
            <body style="font-family: Arial, sans-serif; line-height: 1.6;">
                <p>Good evening,</p>
                <p style="color:#333;">
                    End-of-day summary: <strong>{len(on_hold_orders)} order(s)</strong> currently on hold.
                </p>
                
                <p style="font-weight: bold; margin-top: 20px;">On Hold Orders:</p>
                <table style="width: 100%; border-collapse: collapse; margin: 10px 0;">
                    <thead>
                        <tr style="background-color: #f5f5f5;">
                            <th style="padding: 10px; border: 1px solid #ddd; text-align: left;">Order ID</th>
                            <th style="padding: 10px; border: 1px solid #ddd; text-align: left;">Customer</th>
                            <th style="padding: 10px; border: 1px solid #ddd; text-align: left;">Created By</th>
                            <th style="padding: 10px; border: 1px solid #ddd; text-align: left;">Days On Hold</th>
                            <th style="padding: 10px; border: 1px solid #ddd; text-align: center;">Action</th>
                        </tr>
                    </thead>
                    <tbody>
                        {order_list_html}
                    </tbody>
                </table>
                
                <p style="margin-top: 20px; color:#666; font-size: 12px;">
                    This is an automated daily summary. Please review held orders and take necessary action.
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
                now=True
            )
            frappe.logger().info(f"Evening on hold notification sent to {email}")
        except Exception as e:
            frappe.log_error(
                f"Failed to send evening on hold notification to {email}: {str(e)}",
                "Evening On Hold Notification Error"
            )
    
    frappe.db.commit()