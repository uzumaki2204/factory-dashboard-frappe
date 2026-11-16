"""Install checks and default dashboard configuration."""
import frappe
from factory_dashboard.i18n import message


def before_install():
    for doctype in ("Factory Device", "Production Line", "Line Group", "Productivity Report", "QC Inspection Event"):
        if not frappe.db.exists("DocType", doctype):
            frappe.throw(message("error.missing_doctype", doctype=doctype))
    if not frappe.db.exists("Role", "Productivity Dashboard Manager"):
        frappe.get_doc({"doctype": "Role", "role_name": "Productivity Dashboard Manager", "desk_access": 1}).insert(ignore_permissions=True)


def after_migrate():
    if not frappe.db.exists("Productivity Dashboard Settings", "GLOBAL"):
        frappe.get_doc({"doctype": "Productivity Dashboard Settings", "settings_key": "GLOBAL", "defect_rate_mode": "qc_input"}).insert(ignore_permissions=True)
    frappe.clear_cache()
