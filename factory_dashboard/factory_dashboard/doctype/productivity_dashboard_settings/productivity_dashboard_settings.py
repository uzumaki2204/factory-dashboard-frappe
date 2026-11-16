import frappe
from frappe.model.document import Document
from factory_dashboard.i18n import message


class ProductivityDashboardSettings(Document):
    def validate(self):
        if self.settings_key != "GLOBAL":
            frappe.throw(message("error.invalid_input"))
