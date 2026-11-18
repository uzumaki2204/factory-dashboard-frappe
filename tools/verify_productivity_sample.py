"""Create isolated Productivity records, compare Pilot APIs, then remove them.

Requires FRAPPE_USER/FRAPPE_PASSWORD or FRAPPE_API_TOKEN. The script only
deletes the UUIDs it creates, including on a failed comparison.
"""

import argparse
import json
import os
import sys
import uuid
from datetime import date, timedelta
from http.cookiejar import CookieJar
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import quote, urlencode
from urllib.request import HTTPCookieProcessor, Request, build_opener


SAMPLES = (
    {"planned": 1200, "target": 500, "workers": 20, "ironing": 3,
     "quantities": (80, 100, 120, 140, 0, 0)},
    {"planned": 900, "target": 400, "workers": 15, "ironing": 2,
     "quantities": (50, 70, 80, 100, 0, 0)},
)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    parser.add_argument("--device-id", required=True)
    parser.add_argument("--day", required=True)
    parser.add_argument("--product-code", default="217H005B")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    day = date.fromisoformat(args.day)
    if day >= date.today():
        parser.error("The sample day must be in the past so the target is stable.")
    reference = json.loads((Path(__file__).resolve().parents[1] /
                            "tests/reference/dotnet.json").read_text(encoding="utf-8"))
    sample_calculations = reference["sample_calculations"]

    token = os.environ.get("FRAPPE_API_TOKEN")
    if not token and not all(os.environ.get(key) for key in ("FRAPPE_USER", "FRAPPE_PASSWORD")):
        parser.error("Set FRAPPE_API_TOKEN or FRAPPE_USER and FRAPPE_PASSWORD.")
    opener = build_opener(HTTPCookieProcessor(CookieJar()))
    base = args.url.rstrip("/")

    def request(path, params=None, body=None, method="GET"):
        url = base + quote(path, safe="/%")
        if params:
            url += "?" + urlencode({key: json.dumps(value) if isinstance(value, (list, dict)) else value
                                    for key, value in params.items()})
        headers = {"Accept": "application/json"}
        if token:
            headers["Authorization"] = "token " + token
        data = urlencode(body).encode("utf-8") if body is not None else None
        if data is not None:
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        with opener.open(Request(url, data=data, headers=headers, method=method), timeout=30) as response:
            return json.load(response)

    if not token:
        request("/api/method/login", body={"usr": os.environ["FRAPPE_USER"],
                                           "pwd": os.environ["FRAPPE_PASSWORD"]}, method="POST")

    bootstrap = request("/api/method/factory_productivity.api.bootstrap",
                        {"device_id": args.device_id})["message"]
    profile = request("/api/method/factory_dashboard.api.profile",
                      {"device_id": args.device_id})["message"]
    lines = [row["name"] for row in bootstrap["lines"]
             if row["name"] in profile["scope_lines"]]
    if len(lines) < 2:
        raise RuntimeError("The device needs two assigned lines for this sample.")
    lines = lines[:2]
    slots = sorted(bootstrap["time_slots"], key=lambda row: (row["sort_order"], row["start_time"]))
    if len(slots) < 6:
        raise RuntimeError("The device company needs at least six time slots.")
    slots = slots[:6]
    product = next((row for row in bootstrap["products"]
                    if row["product_code"] == args.product_code), None)
    if not product:
        raise RuntimeError("The sample product code is not active on this site.")

    def resource(doctype, fields, filters):
        return request("/api/resource/" + quote(doctype, safe=""),
                       {"fields": fields, "filters": filters, "limit_page_length": 100})["data"]

    groups = resource("Line Group Assignment", ["line_group"],
                      {"line": lines[0], "is_active": 1})
    combined_group = None
    if not profile["config"]:
        for group in groups:
            members = resource("Line Group Assignment", ["line"],
                               {"line_group": group["line_group"], "is_active": 1})
            if {item["line"] for item in members} == set(lines):
                combined_group = group["line_group"]
                break

    for line in lines:
        if resource("Productivity Production Plan", ["name"],
                    {"line": line, "is_deleted": 0,
                     "closed_production_date": ["is", "not set"]}):
            raise RuntimeError("An open production plan already exists on a sample line.")
        if resource("Productivity Report", ["name"],
                    {"line": line, "production_date": args.day, "is_deleted": 0}):
            raise RuntimeError("A report already exists on the sample date and line.")

    created = []
    observed = {"day": args.day, "product_code": args.product_code, "lines": lines,
                "slots": [row["name"] for row in slots], "expected": {},
                "actual": {}, "differences": [], "cleanup": []}

    def compare(path, actual, expected):
        if actual != expected:
            observed["differences"].append({"path": path, "expected": expected, "actual": actual})

    try:
        for line, sample in zip(lines, SAMPLES):
            plan_id = str(uuid.uuid4())
            created.append(("Productivity Production Plan", plan_id))
            plan = request("/api/method/factory_productivity.api.save_plan",
                           body={"device_id": args.device_id, "values": json.dumps({
                               "name": plan_id, "line": line, "product": product["name"],
                               "line_start_date": (day - timedelta(days=1)).isoformat(),
                               "shipment_date": (day + timedelta(days=1)).isoformat(),
                               "planned_quantity": sample["planned"],
                           })}, method="POST")["message"]["data"]
            compare(f"{line}.plan_id", plan["name"], plan_id)
            available = request("/api/method/factory_productivity.api.open_plans",
                                {"device_id": args.device_id, "production_date": args.day,
                                 "line": line})["message"]
            compare(f"{line}.plan_in_report_picker",
                    plan_id in {row["name"] for row in available}, True)

            report_id = str(uuid.uuid4())
            created.append(("Productivity Report", report_id))
            report = request("/api/method/factory_productivity.api.save_report",
                             body={"device_id": args.device_id, "values": json.dumps({
                                 "name": report_id, "line": line, "product": product["name"],
                                 "production_plan": plan_id, "production_date": args.day,
                                 "daily_target_quantity": sample["target"], "working_hours": 8,
                                 "worker_count": sample["workers"],
                                 "ironing_delivery_quantity": sample["ironing"],
                                 "time_slots": [{"time_slot": slot["name"], "finished_quantity": quantity}
                                                for slot, quantity in zip(slots, sample["quantities"])],
                             }, ensure_ascii=False)}, method="POST")["message"]["data"]
            compare(f"{line}.report_id", report["name"], report_id)
            source = request("/api/resource/Productivity Report/" + report_id)["data"]
            actual_quantities = [int(row["finished_quantity"]) for row in source["time_slots"]]
            compare(f"{line}.report_quantities", actual_quantities, list(sample["quantities"]))

        report_list = request("/api/method/factory_productivity.api.list_reports",
                              {"device_id": args.device_id, "from_date": args.day,
                               "to_date": args.day, "page_size": 50})["message"]
        expected_names = sorted(name for doctype, name in created if doctype == "Productivity Report")
        compare("report_list.names", sorted(row["name"] for row in report_list["items"]),
                expected_names)
        summary = request("/api/method/factory_dashboard.api.summary",
                          {"device_id": args.device_id, "production_date": args.day})["message"]
        display = request("/api/method/factory_dashboard.api.display",
                          {"device_id": args.device_id, "production_date": args.day})["message"]
        observed["actual"]["mode"] = summary["defect_rate_mode"]
        observed["actual"]["display_mode"] = display["display_mode"]
        observed["actual"]["display_lines"] = [row["source_lines"] for row in display["lines"]]

        for line, sample in zip(lines, SAMPLES):
            row = next(item for item in summary["lines"] if item["line"] == line)
            quantities = list(sample["quantities"])
            cumulative = []
            for quantity in quantities:
                cumulative.append((cumulative[-1] if cumulative else 0) + quantity)
            total = sum(quantities)
            expected = {
                "product_code": args.product_code,
                "planned_quantity": sample["planned"], "report_count": 1,
                "finished_quantity": total, "daily_target_quantity": sample["target"],
                "current_target_quantity": sample_calculations[line]["current_target_quantity"],
                "achievement_rate_percent": sample_calculations[line]["achievement_rate_percent"],
                "worker_count": sample["workers"], "working_hours": 8,
                "ironing_delivery_quantity": sample["ironing"],
                "slot_quantities": quantities, "slot_cumulative": cumulative,
            }
            actual = {key: row.get(key) for key in expected if not key.startswith("slot_")}
            actual["slot_quantities"] = [int(slot["quantity"]) for slot in row["time_slots"][:6]]
            actual["slot_cumulative"] = [int(slot["cumulative_quantity"]) for slot in row["time_slots"][:6]]
            for key, value in expected.items():
                compare(f"{line}.{key}", actual[key], value)
            # .NET returns an available zero-percent rate when the source has no inspections.
            if row["qc_total_quantity"] == 0 and row["defect_quantity"] == 0:
                compare(f"{line}.defect_rate_percent", row["defect_rate_percent"], 0.0)
                compare(f"{line}.has_defect_rate", row["has_defect_rate"], True)
            observed["expected"][line] = expected
            observed["actual"][line] = actual | {
                "qc_total_quantity": row["qc_total_quantity"],
                "defect_quantity": row["defect_quantity"],
                "defect_rate_percent": row["defect_rate_percent"],
                "has_defect_rate": row["has_defect_rate"],
            }

        if not profile["config"] and display["lines"]:
            home = profile["home_line"]
            if home in lines:
                panel = display["lines"][0]
                expected_home = observed["expected"][home]
                for key in ("product_code", "planned_quantity", "finished_quantity",
                            "daily_target_quantity", "current_target_quantity"):
                    compare(f"display.{key}", panel.get(key), expected_home[key])

        if combined_group:
            config_id = args.device_id
            created.append(("Productivity Dashboard Device Config", config_id))
            request("/api/resource/Productivity Dashboard Device Config",
                    body={"data": json.dumps({
                        "doctype": "Productivity Dashboard Device Config",
                        "device": args.device_id, "display_mode": "single",
                        "single_group": combined_group,
                    })}, method="POST")
            combined = request("/api/method/factory_dashboard.api.display",
                               {"device_id": args.device_id, "production_date": args.day})["message"]
            panel = combined["lines"][0]
            quantities = [sum(values) for values in zip(*(sample["quantities"] for sample in SAMPLES))]
            cumulative = []
            for quantity in quantities:
                cumulative.append((cumulative[-1] if cumulative else 0) + quantity)
            expected_panel = {
                "product_code": args.product_code, "mixed_products": False,
                "planned_quantity": sum(sample["planned"] for sample in SAMPLES),
                "finished_quantity": sum(quantities),
                "daily_target_quantity": sum(sample["target"] for sample in SAMPLES),
                "current_target_quantity": sample_calculations["combined"]["current_target_quantity"],
                "worker_count": sum(sample["workers"] for sample in SAMPLES),
                "slot_quantities": quantities, "slot_cumulative": cumulative,
            }
            expected_panel["achievement_rate_percent"] = sample_calculations[
                "combined"]["achievement_rate_percent"]
            actual_panel = {key: panel.get(key) for key in expected_panel if not key.startswith("slot_")}
            actual_panel["slot_quantities"] = [slot["quantity"] for slot in panel["time_slots"][:6]]
            actual_panel["slot_cumulative"] = [slot["cumulative_quantity"] for slot in panel["time_slots"][:6]]
            for key, value in expected_panel.items():
                compare(f"combined.{key}", actual_panel[key], value)
            observed["expected"]["combined"] = expected_panel
            observed["actual"]["combined"] = actual_panel
    except Exception as exc:
        observed["error"] = f"{type(exc).__name__}: {exc}"
    finally:
        for doctype, name in reversed(created):
            try:
                request("/api/resource/" + quote(doctype, safe="") + "/" + quote(name, safe=""),
                        method="DELETE")
                observed["cleanup"].append({"doctype": doctype, "name": name, "deleted": True})
            except HTTPError as exc:
                observed["cleanup"].append({"doctype": doctype, "name": name,
                                            "deleted": exc.code == 404, "http_status": exc.code})
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(observed, ensure_ascii=False, indent=2) + "\n",
                                   encoding="utf-8")
        print(json.dumps(observed, ensure_ascii=False, indent=2))
    return 1 if observed["differences"] or observed.get("error") or any(
        not item["deleted"] for item in observed["cleanup"]) else 0


if __name__ == "__main__":
    sys.exit(main())
