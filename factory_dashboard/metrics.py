"""Productivity and source-specific quality projections for dashboard panels."""

from collections import defaultdict
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP

import frappe
from factory_management.api import _time_zone

from factory_dashboard.i18n import message


def _rate(defects, checked, mode):
    if not checked:
        return None
    precision = Decimal("0.1") if mode == "uqqc_input" else Decimal("0.01")
    return float((Decimal(defects) * 100 / Decimal(checked)).quantize(precision, rounding=ROUND_HALF_UP))


def _qc1(device_name):
    name = str(device_name or "").strip()
    return len(name) >= 6 and name[3:6].upper() == "QC1"


def _events(doctype, fields, filters, order_by="name asc"):
    offset = 0
    while True:
        batch = frappe.get_all(
            doctype, fields=fields, filters=filters, order_by=order_by,
            start=offset, limit_page_length=2000,
        )
        yield from batch
        if len(batch) < 2000:
            return
        offset += len(batch)


def _quality(line, product, production_date, mode):
    if not product:
        return 0, 0, 0
    if mode == "uqqc_input":
        if not frappe.db.exists("DocType", "UQQC Inspection Event"):
            frappe.throw(message("error.defect_source"))
        day = date.fromisoformat(production_date)
        start = datetime.combine(day, time.min, _time_zone()).astimezone(timezone.utc)
        finish = datetime.combine(day + timedelta(days=1), time.min, _time_zone()).astimezone(timezone.utc)
        events = list(_events(
            "UQQC Inspection Event", ["event_kind", "quantity"],
            [["line", "=", line], ["product", "=", product],
             ["occurred_at", ">=", start.strftime("%Y-%m-%d %H:%M:%S.%f")],
             ["occurred_at", "<", finish.strftime("%Y-%m-%d %H:%M:%S.%f")]],
        ))
        passed = sum(int(row.quantity or 0) for row in events if row.event_kind == "pass")
        defects = sum(int(row.quantity or 0) for row in events if row.event_kind == "defect")
        return max(0, passed + defects), max(0, defects), sum(1 for row in events if row.event_kind == "defect")

    events = list(_events(
        "QC Inspection Event", ["device", "event_type", "quantity_delta", "defect"],
        {"line": line, "product": product, "server_date_key": production_date},
        order_by="occurred_at asc, creation asc, name asc",
    ))
    device_names = {row.device for row in events if row.device}
    qc1_devices = {row.name for row in frappe.get_all(
        "Factory Device", fields=["name", "device_name"],
        filters={"name": ["in", list(device_names)]}, limit_page_length=len(device_names),
    ) if _qc1(row.device_name)} if device_names else set()
    checked = 0
    by_defect = defaultdict(int)
    defect_events = 0
    for row in events:
        if row.device not in qc1_devices:
            continue
        delta = int(row.quantity_delta or 0)
        if row.event_type in ("CumulativeAdd", "CumulativeSubtract"):
            checked = max(0, checked + delta)
        elif row.defect and row.event_type in ("DefectAdd", "DefectSubtract"):
            by_defect[row.defect] = max(0, by_defect[row.defect] + delta)
            if delta > 0:
                defect_events += 1
    return checked, sum(by_defect.values()), defect_events


def _plan(line, production_date, report):
    if report and report.production_plan:
        rows = frappe.get_all(
            "Productivity Production Plan",
            fields=["name", "product", "line_start_date", "shipment_date", "planned_quantity"],
            filters={"name": report.production_plan, "is_deleted": 0}, limit_page_length=1,
        )
        if rows:
            return rows[0]
    rows = frappe.get_all(
        "Productivity Production Plan",
        fields=["name", "product", "line_start_date", "shipment_date", "closed_production_date", "planned_quantity"],
        filters={"line": line, "is_deleted": 0, "line_start_date": ["<=", production_date]},
        order_by="line_start_date desc, modified desc", limit_page_length=200,
    )
    return next((row for row in rows if str(row.closed_production_date or row.shipment_date) >= production_date), None)


def _slots(company, reports):
    slots = frappe.get_all(
        "Time Slot", fields=["name", "slot_name", "start_time", "end_time", "sort_order"],
        filters={"company": company}, order_by="sort_order asc, start_time asc", limit_page_length=200,
    ) if company else []
    quantities = defaultdict(int)
    names = [row.name for row in reports]
    if names:
        for row in frappe.get_all(
            "Productivity Report Time Slot", fields=["time_slot", "finished_quantity"],
            filters={"parent": ["in", names], "parenttype": "Productivity Report"},
            limit_page_length=10000,
        ):
            quantities[row.time_slot] += int(row.finished_quantity or 0)
    result = []
    cumulative = 0
    for slot in slots:
        quantity = quantities.pop(slot.name, 0)
        cumulative += quantity
        result.append({"time_slot": slot.name, "label": slot.slot_name,
                       "start_time": str(slot.start_time), "end_time": str(slot.end_time),
                       "sort_order": int(slot.sort_order or 0), "quantity": quantity,
                       "cumulative_quantity": cumulative})
    for name, quantity in sorted(quantities.items()):
        cumulative += quantity
        result.append({"time_slot": name, "label": name, "start_time": "", "end_time": "",
                       "sort_order": len(result) + 1, "quantity": quantity,
                       "cumulative_quantity": cumulative})
    return result


def line_summary(line, production_date, mode):
    line_doc = frappe.db.get_value("Production Line", line, ["line_name", "company"], as_dict=True) or {}
    reports = frappe.get_all(
        "Productivity Report",
        fields=["name", "product", "production_plan", "daily_target_quantity", "worker_count",
                "working_hours", "ironing_delivery_quantity"],
        filters={"line": line, "production_date": production_date, "is_deleted": 0},
        order_by="modified desc", limit_page_length=10000,
    )
    selected = reports[0] if reports else None
    plan = _plan(line, production_date, selected)
    product = selected.product if selected else (plan.product if plan else None)
    selected_reports = [row for row in reports if row.product == product]
    time_slots = _slots(line_doc.get("company"), selected_reports)
    checked, defects, defect_events = _quality(line, product, production_date, mode)
    rate = _rate(defects, checked, mode)
    line_info = frappe.get_all(
        "Productivity Line Info", fields=["line_leader_name", "technical_leader_name"],
        filters={"line": line, "is_deleted": 0}, order_by="modified desc", limit_page_length=1,
    )
    product_code = frappe.db.get_value("Product", product, "product_code") if product else ""
    target = sum(int(row.daily_target_quantity or 0) for row in selected_reports)
    finished = sum(row["quantity"] for row in time_slots)
    return {
        "line": line, "line_name": line_doc.get("line_name") or line,
        "production_date": production_date, "product_code": product_code or "",
        "production_plan": plan.name if plan else None,
        "plan_start_date": str(plan.line_start_date) if plan else None,
        "plan_shipment_date": str(plan.shipment_date) if plan else None,
        "planned_quantity": int(plan.planned_quantity or 0) if plan else 0,
        "report_count": len(selected_reports), "finished_quantity": finished,
        "daily_target_quantity": target,
        "achievement_rate_percent": _rate(finished, target, "qc_input") or 0,
        "worker_count": sum(int(row.worker_count or 0) for row in selected_reports),
        "working_hours": sum(float(row.working_hours or 0) for row in selected_reports),
        "ironing_delivery_quantity": sum(int(row.ironing_delivery_quantity or 0) for row in selected_reports),
        "line_leader_name": line_info[0].line_leader_name if line_info else "",
        "technical_leader_name": line_info[0].technical_leader_name if line_info else "",
        "qc_total_quantity": checked, "defect_quantity": defects, "defect_events": defect_events,
        "defect_rate_percent": rate, "has_defect_rate": rate is not None,
        "defect_rate_unavailable_reason": None if rate is not None else message(
            "ui.no_product" if not product else "ui.no_quality_data"),
        "time_slots": time_slots,
    }


def panel_summary(lines, label, production_date, mode):
    entries = [line_summary(line, production_date, mode) for line in lines]
    products = {entry["product_code"] for entry in entries if entry["product_code"]}
    mixed = len(products) > 1 or (len(entries) > 1 and any(not entry["product_code"] for entry in entries))
    checked = sum(entry["qc_total_quantity"] for entry in entries)
    defects = sum(entry["defect_quantity"] for entry in entries)
    slots = defaultdict(int)
    definitions = {}
    for entry in entries:
        for row in entry["time_slots"]:
            slots[row["time_slot"]] += row["quantity"]
            definitions[row["time_slot"]] = row
    cumulative = 0
    time_slots = []
    for key in sorted(slots, key=lambda slot: (definitions[slot]["sort_order"], definitions[slot]["start_time"], slot)):
        row = dict(definitions[key])
        row["quantity"] = slots[key]
        cumulative += slots[key]
        row["cumulative_quantity"] = cumulative
        time_slots.append(row)
    rate = None if mixed else _rate(defects, checked, mode)
    return {
        "line": lines[0] if len(lines) == 1 else None,
        "line_name": label or (entries[0]["line_name"] if len(entries) == 1 else ""),
        "source_lines": lines, "line_details": entries,
        "production_date": production_date, "product_code": next(iter(products)) if len(products) == 1 and not mixed else "",
        "mixed_products": mixed,
        "report_count": sum(entry["report_count"] for entry in entries),
        "finished_quantity": sum(entry["finished_quantity"] for entry in entries),
        "daily_target_quantity": sum(entry["daily_target_quantity"] for entry in entries),
        "planned_quantity": sum(entry["planned_quantity"] for entry in entries),
        "worker_count": sum(entry["worker_count"] for entry in entries),
        "working_hours": sum(entry["working_hours"] for entry in entries),
        "ironing_delivery_quantity": sum(entry["ironing_delivery_quantity"] for entry in entries),
        "achievement_rate_percent": _rate(sum(entry["finished_quantity"] for entry in entries),
                                           sum(entry["daily_target_quantity"] for entry in entries), "qc_input") or 0,
        "line_leader_name": entries[0]["line_leader_name"] if len(entries) == 1 else "",
        "technical_leader_name": entries[0]["technical_leader_name"] if len(entries) == 1 else "",
        "qc_total_quantity": checked, "defect_quantity": defects,
        "defect_events": sum(entry["defect_events"] for entry in entries),
        "defect_rate_percent": rate, "has_defect_rate": rate is not None,
        "defect_rate_unavailable_reason": None if rate is not None else message(
            "ui.mixed_products" if mixed else "ui.no_quality_data"),
        "time_slots": time_slots,
    }
