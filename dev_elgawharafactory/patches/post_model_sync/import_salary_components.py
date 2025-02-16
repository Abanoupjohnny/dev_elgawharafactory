import os

import frappe
from frappe.core.doctype.data_import.data_import import import_doc


def execute():
    salary_components_path = os.path.join(frappe.get_app_path("dev_elgawharafactory", "data_import"), "salary_components.json")
    try:
        import_doc(salary_components_path)
    except (ImportError, frappe.DoesNotExistError) as e:
        # fixture syncing for missing doctypes
        print(f"Skipping fixture syncing from the file salary_components Reason: {e}")
