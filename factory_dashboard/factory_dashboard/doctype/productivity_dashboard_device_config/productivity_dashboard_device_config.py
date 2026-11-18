import frappe
from frappe.model.document import Document
from factory_dashboard.i18n import message


class ProductivityDashboardDeviceConfig(Document):
    def validate(self):
        device = frappe.db.get_value(
            "Factory Device", self.device, ["company", "factory"], as_dict=True,
        )
        if not device:
            frappe.throw(message("error.device_missing"))

        mode = (self.display_mode or "single").strip().lower()
        if mode not in ("single", "dual"):
            frappe.throw(message("error.mode_invalid"))

        left_lines = _validate_screen(self, "left", device, required=True)
        right_lines = _validate_screen(self, "right", device, required=mode == "dual")
        if mode == "dual" and left_lines.intersection(right_lines):
            frappe.throw(message("error.dual_overlap"))


def _validate_screen(document, side, device, required):
    line = getattr(document, f"{side}_line", None)
    group = getattr(document, f"{side}_group", None)
    if line and group:
        frappe.throw(message("error.screen_selection"))
    if not line and not group:
        if required:
            frappe.throw(message("error.left_required" if side == "left" else "error.dual_required"))
        return set()

    if group:
        group_doc = frappe.db.get_value(
            "Line Group", group, ["company", "factory", "is_active"], as_dict=True,
        )
        _validate_scope(group_doc, device)
        lines = {
            row.line for row in frappe.get_all(
                "Line Group Assignment", fields=["line"],
                filters={"line_group": group, "is_active": 1}, limit_page_length=200,
            ) if row.line
        }
        if len(lines) != 2:
            frappe.throw(message("error.group_invalid"))
    else:
        lines = {line}

    for line_name in lines:
        line_doc = frappe.db.get_value(
            "Production Line", line_name, ["company", "factory", "is_active"], as_dict=True,
        )
        _validate_scope(line_doc, device)
    return lines


def _validate_scope(document, device):
    if (not document or document.get("company") != device.get("company")
            or document.get("factory") != device.get("factory")
            or not document.get("is_active")):
        frappe.throw(message("error.selection_scope"))
