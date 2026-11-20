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


@frappe.whitelist(methods=["GET"])
def get_available_selections(device):
    """Return valid line and two-line group choices for a device's factory."""
    if not frappe.has_permission("Productivity Dashboard Device Config", "read"):
        frappe.throw(message("error.permission"), frappe.PermissionError)

    device_scope = frappe.db.get_value(
        "Factory Device", device, ["company", "factory"], as_dict=True,
    ) if device else None
    if not device_scope or not device_scope.company or not device_scope.factory:
        frappe.throw(message("error.device_missing"))

    filters = {
        "company": device_scope.company,
        "factory": device_scope.factory,
        "is_active": 1,
    }
    lines = frappe.get_all(
        "Production Line", fields=["name", "line_code", "line_name"],
        filters=filters, order_by="line_code asc", limit_page_length=0,
    )
    active_lines = {line.name for line in lines}
    options = [
        {"key": f"line:{line.name}", "type": "line", "code": line.line_code, "name": line.line_name}
        for line in lines
    ]

    groups = frappe.get_all(
        "Line Group", fields=["name", "group_code", "group_name"],
        filters=filters, order_by="group_code asc", limit_page_length=0,
    )
    if groups:
        assignments = frappe.get_all(
            "Line Group Assignment", fields=["line_group", "line"],
            filters={"line_group": ["in", [group.name for group in groups]], "is_active": 1},
            limit_page_length=0,
        )
        lines_by_group = {group.name: set() for group in groups}
        for assignment in assignments:
            lines_by_group[assignment.line_group].add(assignment.line)
        for group in groups:
            selected_lines = lines_by_group[group.name]
            if len(selected_lines) == 2 and selected_lines.issubset(active_lines):
                options.append({
                    "key": f"group:{group.name}", "type": "group",
                    "code": group.group_code, "name": group.group_name,
                })

    return options


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
