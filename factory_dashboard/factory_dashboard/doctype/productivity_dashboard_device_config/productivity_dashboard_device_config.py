import frappe
from frappe.model.document import Document
from factory_dashboard.i18n import message


class ProductivityDashboardDeviceConfig(Document):
    def validate(self):
        device = frappe.db.get_value("Factory Device", self.device, ["company", "factory", "line"], as_dict=True)
        if not device:
            frappe.throw(message("error.device_missing"))
        for line in (self.primary_line, self.secondary_line, self.left_line, self.right_line):
            if line and frappe.db.get_value("Production Line", line, "factory") != device.factory:
                frappe.throw(message("error.scope"))
        for group in (self.single_group, self.left_group, self.right_group):
            if group and frappe.db.get_value("Line Group", group, "factory") != device.factory:
                frappe.throw(message("error.scope"))
