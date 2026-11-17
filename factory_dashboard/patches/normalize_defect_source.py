"""Replace retired quality sources in the installed GLOBAL settings document."""

import frappe


def execute():
    if not frappe.db.exists("Productivity Dashboard Settings", "GLOBAL"):
        return
    mode = frappe.db.get_value("Productivity Dashboard Settings", "GLOBAL", "defect_rate_mode")
    if mode not in ("qc_input", "uqqc_input"):
        frappe.db.set_value("Productivity Dashboard Settings", "GLOBAL", "defect_rate_mode", "qc_input")
