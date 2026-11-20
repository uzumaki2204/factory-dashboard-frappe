"""Read-only monthly production summary for approved Dashboard devices."""

from collections import defaultdict
from datetime import date, timedelta

import frappe

from factory_dashboard.i18n import message


def _period(date_from, date_to):
    today = date.fromisoformat(frappe.utils.today())
    try:
        pivot = date.fromisoformat(str(date_from or date_to)) if (date_from or date_to) else today
        first = date(pivot.year, pivot.month, 1)
        last = date(pivot.year + (pivot.month == 12), pivot.month % 12 + 1, 1) - timedelta(days=1)
        start = date.fromisoformat(str(date_from)) if date_from else first
        end = date.fromisoformat(str(date_to)) if date_to else last
    except ValueError:
        frappe.throw(message("error.summary_period"), frappe.ValidationError)
    if start > end or (end - start).days > 31:
        frappe.throw(message("error.summary_period"), frappe.ValidationError)
    return start.isoformat(), end.isoformat()


def _filters(company_code, factory_code, product_code):
    values = [str(value or "").strip() for value in (company_code, factory_code, product_code)]
    if any(len(value) > 140 for value in values):
        frappe.throw(message("error.invalid_input"), frappe.ValidationError)
    return dict(zip(("company_code", "factory_code", "product_code"), values))


def _where(filters, dates=True):
    clauses = ["r.is_deleted = 0", "COALESCE(totals.quantity, 0) > 0"]
    if dates:
        clauses.extend(("r.production_date >= %(date_from)s", "r.production_date <= %(date_to)s"))
    for key, column in (("company_code", "c.company_code"),
                        ("factory_code", "f.factory_code"),
                        ("product_code", "p.product_code")):
        if filters[key]:
            clauses.append(f"{column} = %({key})s")
    return " AND ".join(clauses)


_SOURCE = """
    FROM `tabProductivity Report` r
    INNER JOIN `tabProductivity Production Plan` plan ON plan.name = r.production_plan
    INNER JOIN (
        SELECT parent, SUM(finished_quantity) quantity
        FROM `tabProductivity Report Time Slot`
        WHERE parenttype = 'Productivity Report' AND parentfield = 'time_slots'
        GROUP BY parent
    ) totals ON totals.parent = r.name
    LEFT JOIN `tabCompany` c ON c.name = r.company
    LEFT JOIN `tabFactory` f ON f.name = r.factory
    LEFT JOIN `tabProduction Line` l ON l.name = r.line
    LEFT JOIN `tabProduct` p ON p.name = r.product
"""


def _rows(start, end, filters):
    params = {"date_from": start, "date_to": end, **filters}
    return frappe.db.sql("""
        SELECT r.company company_id, COALESCE(c.company_code, r.company) company_code,
               COALESCE(c.company_name, c.company_code, r.company) company_name,
               r.factory factory_id, COALESCE(f.factory_code, r.factory) factory_code,
               COALESCE(f.factory_name, f.factory_code, r.factory) factory_name,
               r.line line_id, COALESCE(l.line_code, r.line) line_code,
               COALESCE(l.line_name, l.line_code, r.line) line_name,
               r.product product_id, COALESCE(p.product_code, r.product) product_code,
               COALESCE(p.product_name, p.product_code, r.product) product_name,
               r.production_date, totals.quantity produced_quantity
    """ + _SOURCE + " WHERE " + _where(filters) + " ORDER BY r.production_date, r.name", params, as_dict=True)


def _lifetime(filters):
    return frappe.db.sql("""
        SELECT r.company company_id, r.factory factory_id, r.line line_id,
               COALESCE(l.line_code, r.line) line_code,
               COALESCE(p.product_code, r.product) product_code,
               SUM(totals.quantity) produced_quantity
    """ + _SOURCE + " WHERE " + _where(filters, dates=False) + """
        GROUP BY r.company, r.factory, r.line, l.line_code, r.product, p.product_code
    """, filters, as_dict=True)


def _line_labels(rows):
    lines = sorted({row.line_id for row in rows if row.line_id})
    if not lines:
        return {}
    assignments = frappe.get_all(
        "Line Group Assignment", fields=["line", "line_group"],
        filters={"line": ["in", lines], "is_active": 1}, limit_page_length=0,
    )
    groups = sorted({row.line_group for row in assignments if row.line_group})
    group_docs = {row.name: row for row in frappe.get_all(
        "Line Group", fields=["name", "group_code", "group_name"],
        filters={"name": ["in", groups], "is_active": 1}, limit_page_length=0,
    )} if groups else {}
    by_line = defaultdict(set)
    for assignment in assignments:
        if assignment.line_group in group_docs:
            by_line[assignment.line].add(assignment.line_group)
    return {line: (group_docs[next(iter(choices))].group_code,
                   group_docs[next(iter(choices))].group_name)
            for line, choices in by_line.items() if len(choices) == 1}


def _label(row, labels):
    return labels.get(row.line_id) or (row.line_code, row.get("line_name") or row.line_code)


def build_summary(date_from=None, date_to=None, company_code=None, factory_code=None, product_code=None):
    start, end = _period(date_from, date_to)
    selected = _filters(company_code, factory_code, product_code)
    option_rows = _rows(start, end, {key: "" for key in selected})
    range_rows = [row for row in option_rows if
                  (not selected["company_code"] or row.company_code == selected["company_code"]) and
                  (not selected["factory_code"] or row.factory_code == selected["factory_code"]) and
                  (not selected["product_code"] or row.product_code == selected["product_code"])]
    lifetime_rows = _lifetime(selected)
    labels = _line_labels(range_rows + lifetime_rows)
    cumulative_product = defaultdict(int)
    cumulative_line = defaultdict(int)
    for row in lifetime_rows:
        line_code, _ = _label(row, labels)
        cumulative_product[row.product_code] += int(row.produced_quantity or 0)
        cumulative_line[(row.company_id, row.factory_id, line_code, row.product_code)] += int(row.produced_quantity or 0)

    entries_by_key = {}
    products = {}
    for row in range_rows:
        line_code, line_name = _label(row, labels)
        key = (row.company_id, row.factory_id, line_code, row.product_code, str(row.production_date))
        if key not in entries_by_key:
            entries_by_key[key] = {
                "company_code": row.company_code, "company_name": row.company_name,
                "factory_code": row.factory_code, "factory_name": row.factory_name,
                "line_code": line_code, "line_name": line_name,
                "product_code": row.product_code, "product_name": row.product_name,
                "production_date": str(row.production_date), "produced_quantity": 0,
                "cumulative_produced": cumulative_line[(row.company_id, row.factory_id, line_code, row.product_code)],
            }
        entries_by_key[key]["produced_quantity"] += int(row.produced_quantity or 0)
        product = products.setdefault(row.product_code, {"code": row.product_code,
            "name": row.product_name, "total_produced": 0,
            "cumulative_produced": cumulative_product[row.product_code]})
        product["total_produced"] += int(row.produced_quantity or 0)

    companies = {(row.company_code, row.company_name) for row in option_rows}
    factories = {(row.company_code, row.factory_code, row.factory_name) for row in option_rows}
    product_options = {(row.company_code, row.factory_code, row.product_code, row.product_name) for row in option_rows}
    return {
        "date_from": start, "date_to": end, "filters": selected,
        "companies": [{"code": code, "name": name} for code, name in sorted(companies)],
        "factories": [{"company_code": company, "code": code, "name": name}
                      for company, code, name in sorted(factories)],
        "products": [{"company_code": company, "factory_code": factory, "code": code, "name": name}
                     for company, factory, code, name in sorted(product_options)],
        "product_totals": sorted(products.values(), key=lambda item: (-item["total_produced"], item["code"])),
        "entries": sorted(entries_by_key.values(), key=lambda item:
                          (item["company_code"], item["factory_code"], item["production_date"],
                           item["line_code"], item["product_code"])),
        "generated_at": frappe.utils.now_datetime().isoformat(),
    }
