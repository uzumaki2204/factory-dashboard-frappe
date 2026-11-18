"""Read-only comparison of deployed summary against local metrics over site source rows.

Credentials are read from FRAPPE_USER / FRAPPE_PASSWORD, or FRAPPE_API_TOKEN.
The only POST is login; source data is read exclusively through GET requests.
"""
import argparse
import importlib
import json
import os
import sys
import types
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import quote, urlencode
from urllib.request import HTTPCookieProcessor, Request, build_opener
from http.cookiejar import CookieJar


class Row(dict):
    __getattr__ = dict.get


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--url', required=True)
    parser.add_argument('--device-id', required=True)
    parser.add_argument('--day', required=True)
    args = parser.parse_args()
    opener = build_opener(HTTPCookieProcessor(CookieJar()))
    token = os.environ.get('FRAPPE_API_TOKEN')

    def request(path, params=None, login=None):
        headers = {'Accept': 'application/json'}
        if token:
            headers['Authorization'] = 'token ' + token
        data = urlencode(login).encode() if login else None
        url = args.url.rstrip('/') + quote(path, safe='/%')
        if params:
            url += '?' + urlencode({k: json.dumps(v) if isinstance(v, (dict, list)) else v for k, v in params.items()})
        with opener.open(Request(url, data=data, headers=headers), timeout=30) as response:
            return json.load(response)

    if not token:
        request('/api/method/login', login={'usr': os.environ['FRAPPE_USER'], 'pwd': os.environ['FRAPPE_PASSWORD']})

    def get_all(doctype, fields=None, filters=None, order_by=None, start=0, limit_page_length=20, **kwargs):
        if doctype == 'Productivity Report Time Slot':
            return [Row(row) for parent in filters['parent'][1]
                    for row in request('/api/resource/Productivity Report/' + quote(parent, safe=''))['data'].get('time_slots', [])]
        params = {'fields': fields or ['name'], 'filters': filters or {}, 'limit_start': start,
                  'limit_page_length': limit_page_length or 100000}
        if order_by:
            params['order_by'] = order_by
        return [Row(row) for row in request('/api/resource/' + quote(doctype, safe=''), params)['data']]

    def get_value(doctype, name, fields=None, as_dict=False):
        rows = get_all(doctype, fields=[fields] if isinstance(fields, str) else fields,
                       filters=name if isinstance(name, dict) else {'name': name}, limit_page_length=1)
        if not rows:
            return None
        return rows[0] if as_dict else rows[0].get(fields or 'name')

    def exists(doctype, name):
        try:
            return bool(get_value(doctype, name))
        except HTTPError as error:
            if error.code == 404:
                return False
            raise

    frappe = types.ModuleType('frappe')
    frappe.get_all = get_all
    frappe.db = Row(get_value=get_value, exists=exists)
    frappe.form_dict = {}
    frappe.local = Row(lang='vi')
    frappe.throw = lambda message: (_ for _ in ()).throw(ValueError(message))
    sys.modules['frappe'] = frappe
    sys.modules['factory_management'] = types.ModuleType('factory_management')
    master = types.ModuleType('factory_management.api')
    # Match the site's System Settings time zone; UTC+07 fallback is never host-dependent.
    from zoneinfo import ZoneInfo
    try:
        settings = request('/api/resource/System Settings/System Settings')['data']
        zone = ZoneInfo(settings.get('time_zone') or 'Asia/Ho_Chi_Minh')
    except (HTTPError, KeyError):
        zone = timezone(timedelta(hours=7))
    master._time_zone = lambda: zone
    sys.modules['factory_management.api'] = master
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    metrics = importlib.import_module('factory_dashboard.metrics')
    deployed = request('/api/method/factory_dashboard.api.summary', {'device_id': args.device_id, 'production_date': args.day})['message']
    checked_fields = ['product_code','planned_quantity','finished_quantity','daily_target_quantity',
                      'worker_count','working_hours','ironing_delivery_quantity','qc_total_quantity',
                      'defect_quantity','defect_rate_percent','has_defect_rate']
    differences = []
    report_count = 0
    for row in deployed['lines']:
        local = metrics.line_summary(row['line'], args.day, deployed['defect_rate_mode'])
        report_count += local['report_count']
        for field in checked_fields:
            if row.get(field) != local.get(field):
                differences.append({'line': row['line'], 'field': field, 'deployed': row.get(field), 'expected': local.get(field)})
        source_slots = [(s['time_slot'],s['quantity'],s['cumulative_quantity']) for s in local['time_slots']]
        deployed_slots = [(s['time_slot'],s['quantity'],s['cumulative_quantity']) for s in row['time_slots']]
        if source_slots != deployed_slots:
            differences.append({'line':row['line'],'field':'time_slots'})
    print(json.dumps({'day':args.day,'lines_checked':len(deployed['lines']),'reports_selected':report_count,
                      'mode':deployed['defect_rate_mode'],'differences':differences},ensure_ascii=True,indent=2))
    return 1 if differences else 0


if __name__ == '__main__':
    raise SystemExit(main())
