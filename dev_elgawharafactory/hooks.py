app_name = "dev_elgawharafactory"
app_title = "Dev Elgawharafactory"
app_publisher = "Abanoub Johnny"
app_description = "Dev Elgawharafactory bBy ENG: Abanoub"
app_email = "bebo_johnny@hotmail.com"
app_license = "mit"
# required_apps = []

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/dev_elgawharafactory/css/dev_elgawharafactory.css"
# app_include_js = "/assets/dev_elgawharafactory/js/dev_elgawharafactory.js"

website_context = {
	"favicon": '/assets/dev_elgawharafactory/images/favicon.ico',
	"splash_image": "/assets/dev_elgawharafactory/images/splash-screen.png"
}


# include js, css files in header of web template
# web_include_css = "/assets/dev_elgawharafactory/css/dev_elgawharafactory.css"
# web_include_js = "/assets/dev_elgawharafactory/js/dev_elgawharafactory.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "dev_elgawharafactory/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
# doctype_js = {"doctype" : "public/js/doctype.js"}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "dev_elgawharafactory/public/icons.svg"

# Home Pages
# ----------

# application home page (will override Website Settings)
home_page = "login"

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
# 	"methods": "dev_elgawharafactory.utils.jinja_methods",
# 	"filters": "dev_elgawharafactory.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "dev_elgawharafactory.install.before_install"
# after_install = "dev_elgawharafactory.install.after_install"

# Uninstallation
# ------------

# before_uninstall = "dev_elgawharafactory.uninstall.before_uninstall"
# after_uninstall = "dev_elgawharafactory.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "dev_elgawharafactory.utils.before_app_install"
# after_app_install = "dev_elgawharafactory.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "dev_elgawharafactory.utils.before_app_uninstall"
# after_app_uninstall = "dev_elgawharafactory.utils.after_app_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "dev_elgawharafactory.notifications.get_notification_config"

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

doc_events = {
	"*": {
		"after_submit": "method",
		# "on_update": "method",
		# "on_cancel": "method",
		# "on_trash": "method"
	}
}

# Scheduled Tasks
# ---------------

# scheduler_events = {
# 	"all": [
# 		"dev_elgawharafactory.tasks.all"
# 	],
# 	"daily": [
# 		"dev_elgawharafactory.tasks.daily"
# 	],
# 	"hourly": [
# 		"dev_elgawharafactory.tasks.hourly"
# 	],
# 	"weekly": [
# 		"dev_elgawharafactory.tasks.weekly"
# 	],
# 	"monthly": [
# 		"dev_elgawharafactory.tasks.monthly"
# 	],
# }

# Testing
# -------

# before_tests = "dev_elgawharafactory.install.before_tests"

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "dev_elgawharafactory.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "dev_elgawharafactory.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["dev_elgawharafactory.utils.before_request"]
# after_request = ["dev_elgawharafactory.utils.after_request"]

# Job Events
# ----------
# before_job = ["dev_elgawharafactory.utils.before_job"]
# after_job = ["dev_elgawharafactory.utils.after_job"]

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
# 	"dev_elgawharafactory.auth.validate"
# ]

# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs
# }

