app_name = "autozonepro"
app_title = "Autozonepro"
app_publisher = "Ernest Benedict"
app_description = "All Customizations"
app_email = "ernestben69@gmail.com"
app_license = "mit"

# Apps
# ------------------

# required_apps = []

# Each item in the list will be shown as an app in the apps page
# add_to_apps_screen = [
# 	{
# 		"name": "autozonepro",
# 		"logo": "/assets/autozonepro/logo.png",
# 		"title": "Autozonepro",
# 		"route": "/autozonepro",
# 		"has_permission": "autozonepro.api.permission.has_app_permission"
# 	}
# ]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/autozonepro/css/autozonepro.css"
# app_include_js = "/assets/autozonepro/js/autozonepro.js"

# include js, css files in header of web template
# web_include_css = "/assets/autozonepro/css/autozonepro.css"
# web_include_js = "/assets/autozonepro/js/autozonepro.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "autozonepro/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
doctype_js = {
    "Sales Order": [
        "public/js/hide_sales_order_butttons.js",
        "public/js/update_delivery_note.js",
        "public/js/verify_packing_list.js"
    ],
    "Packing List":[
        "public/js/packing_list_box-entry.js",
        "public/js/js/packing_list_logic.js",
        "public/js/enter_box_details.js",
    ],
    "Delivery Note":[
        "public/js/add_packing_list_on_dn.js"
    ]
}

# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "autozonepro/public/icons.svg"

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
# 	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
# 	"methods": "autozonepro.utils.jinja_methods",
# 	"filters": "autozonepro.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "autozonepro.install.before_install"
# after_install = "autozonepro.install.after_install"

# Uninstallation
# ------------

# before_uninstall = "autozonepro.uninstall.before_uninstall"
# after_uninstall = "autozonepro.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "autozonepro.utils.before_app_install"
# after_app_install = "autozonepro.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "autozonepro.utils.before_app_uninstall"
# after_app_uninstall = "autozonepro.utils.after_app_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "autozonepro.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

# DocType Class
# ---------------
# Override standard doctype classes

# override_doctype_class = {
# 	"ToDo": "custom_app.overrides.CustomToDo"
# }

# Document Events
# ---------------
# Hook on document methods and events

# doc_events = {
# 	"*": {
# 		"on_update": "method",
# 		"on_cancel": "method",
# 		"on_trash": "method"
# 	}
# }

# Scheduled Tasks
# ---------------

# scheduler_events = {
# 	"all": [
# 		"autozonepro.tasks.all"
# 	],
# 	"daily": [
# 		"autozonepro.tasks.daily"
# 	],
# 	"hourly": [
# 		"autozonepro.tasks.hourly"
# 	],
# 	"weekly": [
# 		"autozonepro.tasks.weekly"
# 	],
# 	"monthly": [
# 		"autozonepro.tasks.monthly"
# 	],
# }

# Testing
# -------

# before_tests = "autozonepro.install.before_tests"

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "autozonepro.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "autozonepro.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["autozonepro.utils.before_request"]
# after_request = ["autozonepro.utils.after_request"]

# Job Events
# ----------
# before_job = ["autozonepro.utils.before_job"]
# after_job = ["autozonepro.utils.after_job"]

# User Data Protection
# --------------------

# user_data_fields = [
# 	{
# 		"doctype": "{doctype_1}",
# 		"filter_by": "{filter_by}",
# 		"redact_fields": ["{field_1}", "{field_2}"],
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_2}",
# 		"filter_by": "{filter_by}",
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_3}",
# 		"strict": False,
# 	},
# 	{
# 		"doctype": "{doctype_4}"
# 	}
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"autozonepro.auth.validate"
# ]

# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs
# }

