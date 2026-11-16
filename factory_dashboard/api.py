"""Dashboard projections from current Frappe transactions and QC events."""
from datetime import date

import frappe
from factory_dashboard.i18n import catalog, message
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


def _line_summary(line, production_date, mode):
    reports = frappe.get_all(
        "Productivity Report",
        fields=["name", "daily_target_quantity", "worker_count", "working_hours", "ironing_delivery_quantity"],
        filters={"line": line, "production_date": production_date, "is_deleted": 0},
        limit_page_length=10000,
    )
    total = 0
    slots = {}
    for report in reports:
        for row in frappe.get_all(
            "Productivity Report Time Slot", fields=["time_slot", "finished_quantity"],
            filters={"parent": report.name, "parenttype": "Productivity Report"}, limit_page_length=100,
        ):
            quantity = int(row.finished_quantity or 0)
            total += quantity
            slots[row.time_slot] = slots.get(row.time_slot, 0) + quantity
    qc = frappe.get_all(
        "QC Inspection Event", fields=["event_type", "quantity_delta", "defect"],
        filters={"line": line, "server_date_key": production_date},
        order_by="occurred_at asc", limit_page_length=100000,
    )
    qc_total = 0
    defect_quantity = 0
    defect_events = 0
    for event in qc:
        delta = int(event.quantity_delta or 0)
        if event.event_type in ("CumulativeAdd", "CumulativeSubtract"):
            qc_total = max(0, qc_total + delta)
        elif event.event_type in ("DefectAdd", "DefectSubtract") or event.defect:
            defect_quantity = max(0, defect_quantity + delta)
            if delta > 0:
                defect_events += 1
    rate = (100 * defect_quantity / qc_total) if qc_total else 0
    return {
        "line": line, "line_name": frappe.db.get_value("Production Line", line, "line_name"),
        "production_date": production_date, "report_count": len(reports),
        "finished_quantity": total,
        "daily_target_quantity": sum(int(row.daily_target_quantity or 0) for row in reports),
        "worker_count": sum(int(row.worker_count or 0) for row in reports),
        "working_hours": sum(float(row.working_hours or 0) for row in reports),
        "ironing_delivery_quantity": sum(int(row.ironing_delivery_quantity or 0) for row in reports),
        "qc_total_quantity": qc_total, "defect_quantity": defect_quantity, "defect_events": defect_events,
        "defect_rate_percent": round(rate, 2) if mode == "qc_input" else None,
        "has_defect_rate": mode == "qc_input",
        "defect_rate_unavailable_reason": None if mode == "qc_input" else message("error.defect_source"),
        "time_slots": slots,
    }


def _panel_lines(group, line, fallback):
    if group:
        return [row.line for row in frappe.get_all(
            "Line Group Assignment", fields=["line"],
            filters={"line_group": group, "is_active": 1}, limit_page_length=200,
        )]
    return [line or fallback]


def _panel_summary(lines, label, production_date, mode):
    entries = [_line_summary(line, production_date, mode) for line in lines]
    slots = {}
    for entry in entries:
        for slot, quantity in entry["time_slots"].items():
            slots[slot] = slots.get(slot, 0) + quantity
    qc_total = sum(entry["qc_total_quantity"] for entry in entries)
    defects = sum(entry["defect_quantity"] for entry in entries)
    return {
        "line": lines[0] if len(lines) == 1 else None,
        "line_name": label or (entries[0]["line_name"] if len(entries) == 1 else ""),
        "source_lines": lines,
        "production_date": production_date,
        "report_count": sum(entry["report_count"] for entry in entries),
        "finished_quantity": sum(entry["finished_quantity"] for entry in entries),
        "daily_target_quantity": sum(entry["daily_target_quantity"] for entry in entries),
        "worker_count": sum(entry["worker_count"] for entry in entries),
        "working_hours": sum(entry["working_hours"] for entry in entries),
        "ironing_delivery_quantity": sum(entry["ironing_delivery_quantity"] for entry in entries),
        "qc_total_quantity": qc_total, "defect_quantity": defects,
        "defect_events": sum(entry["defect_events"] for entry in entries),
        "defect_rate_percent": round(100 * defects / qc_total, 2) if mode == "qc_input" and qc_total else (0 if mode == "qc_input" else None),
        "has_defect_rate": mode == "qc_input",
        "defect_rate_unavailable_reason": None if mode == "qc_input" else message("error.defect_source"),
        "time_slots": slots,
    }


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
            "scope_lines": scope_lines(device), "config": values}


@frappe.whitelist(allow_guest=True, methods=["GET"])
def summary(device_id=None, production_date=None, lines=None):
    device = _device(device_id)
    allowed = scope_lines(device)
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
    settings = frappe.db.get_value("Productivity Dashboard Settings", "GLOBAL", "defect_rate_mode") or "qc_input"
    return {"production_date": day, "defect_rate_mode": settings,
            "lines": [_line_summary(line, day, settings) for line in lines]}


@frappe.whitelist(allow_guest=True, methods=["GET"])
def display(device_id=None, production_date=None):
    current = profile(device_id)
    config = current["config"]
    fallback = current["scope_lines"][0]
    if config.get("display_mode") == "dual":
        panels = [
            (config.get("left_group"), config.get("left_line") or config.get("primary_line")),
            (config.get("right_group"), config.get("right_line") or config.get("secondary_line")),
        ]
    else:
        panels = [(config.get("single_group"), config.get("primary_line"))]
    selected = [_panel_lines(group, line, fallback) for group, line in panels]
    if any(not lines or any(line not in current["scope_lines"] for line in lines) for lines in selected):
        _fail("error.scope", frappe.PermissionError)
    day = _date(production_date)
    mode = frappe.db.get_value("Productivity Dashboard Settings", "GLOBAL", "defect_rate_mode") or "qc_input"
    rows = []
    for (group, _), lines in zip(panels, selected):
        label = frappe.db.get_value("Line Group", group, "group_name") if group else None
        rows.append(_panel_summary(lines, label, day, mode))
    return {"production_date": day, "defect_rate_mode": mode,
            "display_mode": config.get("display_mode") or "single", "lines": rows}
