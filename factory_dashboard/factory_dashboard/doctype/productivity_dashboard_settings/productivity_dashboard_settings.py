import frappe
from frappe.model.document import Document
from factory_dashboard.i18n import message


class ProductivityDashboardSettings(Document):
    def validate(self):
        if self.settings_key != "GLOBAL":
            frappe.throw(message("error.invalid_input"))
        if self.defect_rate_mode not in ("qc_input", "uqqc_input"):
            frappe.throw(message("error.invalid_input"))
