"""Device-scoped dashboard APIs for productivity and QC/UQQC projections."""
from datetime import date

import frappe
from factory_dashboard.i18n import catalog, message
from factory_dashboard.metrics import line_summary, panel_summary
from factory_management.device_registry import ready
from factory_productivity.api import scope_lines


def _fail(key, error=frappe.ValidationError):
    frappe.throw(message(key), error)


def _device(device_id):
    if not device_id or not frappe.db.exists("Factory Device", str(device_id)):
        _fail("error.device_missing", frappe.DoesNotExistError)
    device = frappe.get_doc("Factory Device", str(device_id))
    if not ready(device):
        _fail("error.device_pending", frappe.PermissionError)
    return device


def _date(value):
    try:
        return date.fromisoformat(str(value or frappe.utils.today())).isoformat()
    except ValueError:
        _fail("error.invalid_input")


def _settings():
    values = frappe.db.get_value(
        "Productivity Dashboard Settings", "GLOBAL", ["defect_rate_mode", "refresh_seconds"], as_dict=True,
    ) or {}
    mode = values.get("defect_rate_mode")
    if mode not in ("qc_input", "uqqc_input"):
        mode = "qc_input"
    interval = int(values.get("refresh_seconds") or 60)
    return mode, max(10, min(interval, 3600))


def _panel_lines(group, line, fallback):
    if group:
        return [row.line for row in frappe.get_all(
            "Line Group Assignment", fields=["line"],
            filters={"line_group": group, "is_active": 1}, limit_page_length=200,
        )]
    selected_line = line or fallback
    return [selected_line] if selected_line else []


def _screen_selection(config, side, legacy_line=None, legacy_group=None, fallback=None):
    group = config.get(f"{side}_group")
    line = config.get(f"{side}_line")
    if not group and not line:
        group = config.get(legacy_group) if legacy_group else None
        line = config.get(legacy_line) if legacy_line else None
    if group:
        line = None
    if not group and not line and fallback:
        line = fallback
    return group, line


def _validate_panel_scope(group, lines, company, factory):
    if group:
        group_doc = frappe.db.get_value(
            "Line Group", group, ["company", "factory", "is_active"], as_dict=True,
        )
        if (not group_doc or group_doc.get("company") != company
                or group_doc.get("factory") != factory or not group_doc.get("is_active")):
            _fail("error.selection_scope", frappe.PermissionError)
        if len(set(lines)) != 2:
            _fail("error.group_invalid", frappe.PermissionError)

    for line in set(lines):
        line_doc = frappe.db.get_value(
            "Production Line", line, ["company", "factory", "is_active"], as_dict=True,
        )
        if (not line_doc or line_doc.get("company") != company
                or line_doc.get("factory") != factory or not line_doc.get("is_active")):
            _fail("error.selection_scope", frappe.PermissionError)


@frappe.whitelist(allow_guest=True, methods=["GET"])
def translations(lang="vi"):
    values = catalog()
    return values.get(str(lang).split("-")[0], values["vi"])


@frappe.whitelist(allow_guest=True, methods=["GET"])
def profile(device_id=None):
    device = _device(device_id)
    config = frappe.db.get_value("Productivity Dashboard Device Config", {"device": device.name}, "name")
    values = frappe.get_doc("Productivity Dashboard Device Config", config).as_dict() if config else {}
    return {"device": device.name, "company": device.company, "factory": device.factory,
            "home_line": device.line,
            "scope_lines": [line for line in scope_lines(device) if line], "config": values}


@frappe.whitelist(allow_guest=True, methods=["GET"])
def summary(device_id=None, production_date=None, lines=None):
    device = _device(device_id)
    allowed = [line for line in scope_lines(device) if line]
    if isinstance(lines, str):
        try:
            lines = frappe.parse_json(lines)
        except (TypeError, ValueError):
            _fail("error.invalid_input")
    if lines is None:
        lines = allowed
    if not isinstance(lines, list) or any(line not in allowed for line in lines):
        _fail("error.scope", frappe.PermissionError)
    day = _date(production_date)
    mode, refresh_seconds = _settings()
    return {"production_date": day, "defect_rate_mode": mode, "refresh_seconds": refresh_seconds,
            "lines": [line_summary(line, day, mode) for line in lines]}


@frappe.whitelist(allow_guest=True, methods=["GET"])
def display(device_id=None, production_date=None):
    current = profile(device_id)
    config = current["config"]
    if not current["scope_lines"]:
        _fail("error.config_missing")
    fallback = (current["home_line"] if current["home_line"] in current["scope_lines"]
                else current["scope_lines"][0])
    display_mode = (config.get("display_mode") or "single").strip().lower()
    if display_mode == "dual":
        panels = [
            _screen_selection(config, "left", legacy_line="primary_line"),
            _screen_selection(config, "right", legacy_line="secondary_line"),
        ]
        if any(not group and not line for group, line in panels):
            _fail("error.dual_required")
    else:
        display_mode = "single"
        panels = [
            _screen_selection(
                config, "left", legacy_line="primary_line", legacy_group="single_group", fallback=fallback,
            )
        ]
    selected = [_panel_lines(group, line, fallback) for group, line in panels]
    if any(not lines for lines in selected):
        _fail("error.scope", frappe.PermissionError)
    for (group, _), lines in zip(panels, selected):
        _validate_panel_scope(group, lines, current["company"], current["factory"])
    if display_mode == "dual" and set(selected[0]).intersection(selected[1]):
        _fail("error.dual_overlap", frappe.PermissionError)
    day = _date(production_date)
    mode, refresh_seconds = _settings()
    rows = []
    for (group, _), lines in zip(panels, selected):
        label = frappe.db.get_value("Line Group", group, "group_name") if group else None
        rows.append(panel_summary(lines, label, day, mode))
    return {"production_date": day, "defect_rate_mode": mode,
            "refresh_seconds": refresh_seconds,
            "display_mode": display_mode, "lines": rows}
