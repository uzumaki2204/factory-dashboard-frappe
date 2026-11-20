"""Sync the two screen selectors while preserving the stored line and group links."""

import frappe


def execute():
    frappe.reload_doc("factory_dashboard", "doctype", "productivity_dashboard_device_config")
