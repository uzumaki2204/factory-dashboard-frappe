"""Run with python -m unittest discover -s tests -v (no Frappe installation needed)."""
import json
import sys
import types
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

ZONE = timezone(timedelta(hours=7))
REFERENCE = json.loads((Path(__file__).parent / 'reference/dotnet.json').read_text(encoding='utf-8'))


class Row(dict):
    __getattr__ = dict.get


class Clock(datetime):
    point = datetime(2026, 11, 17, 9, 30, tzinfo=ZONE)

    @classmethod
    def now(cls, tz=None):
        return cls.point.astimezone(tz)


frappe = types.ModuleType('frappe')
frappe.local = Row(lang='vi')
frappe.form_dict = {}
frappe.ValidationError = ValueError
frappe.PermissionError = PermissionError
frappe.DoesNotExistError = LookupError
frappe.throw = lambda text, error=ValueError: (_ for _ in ()).throw(error(text))
frappe.whitelist = lambda **kwargs: lambda fn: fn
sys.modules['frappe'] = frappe
master = types.ModuleType('factory_management.api')
master._time_zone = lambda: ZONE
sys.modules.setdefault('factory_management', types.ModuleType('factory_management'))
sys.modules['factory_management.api'] = master
registry = types.ModuleType('factory_management.device_registry')
registry.ready = lambda device: device.status == 'Approved' and device.is_active
sys.modules['factory_management.device_registry'] = registry
productivity = types.ModuleType('factory_productivity.api')
productivity.scope_lines = lambda device: ['L1', 'L2']
sys.modules.setdefault('factory_productivity', types.ModuleType('factory_productivity'))
sys.modules['factory_productivity.api'] = productivity
from factory_dashboard import metrics, api


class ParityTests(unittest.TestCase):
    def setUp(self):
        frappe.db = MagicMock()
        frappe.get_all = MagicMock(return_value=[])
        frappe.get_doc = MagicMock()
        Clock.point = datetime(2026, 11, 17, 9, 30, tzinfo=ZONE)
        self.clock = patch.object(metrics, 'datetime', Clock)
        self.clock.start()
        self.addCleanup(self.clock.stop)

    def test_current_target_matches_actual_dotnet_for_36_time_boundaries(self):
        for case in REFERENCE['targets']:
            with self.subTest(case=case):
                Clock.point = datetime.fromisoformat(case['now']).replace(tzinfo=ZONE)
                self.assertEqual(case['expected'], metrics._current_target(case['day'], case['target'], case['hours']))

    def test_rates_match_dotnet_ratio_rounded_to_four_places_for_both_sources(self):
        for mode in ('qc_input', 'uqqc_input'):
            for case in REFERENCE['rates']:
                with self.subTest(mode=mode, case=case):
                    self.assertEqual(case['percent'], metrics._rate(case['numerator'], case['denominator'], mode))

    def test_slot_visibility_matches_actual_dotnet_at_30_boundaries(self):
        for case in REFERENCE['slots']:
            with self.subTest(case=case):
                Clock.point = datetime.fromisoformat(case['now']).replace(tzinfo=ZONE)
                frappe.get_all.side_effect = lambda dt, **kw: ([Row(name='S1', slot_name='Ca 1', start_time=timedelta(hours=7, minutes=30), end_time=timedelta(hours=9, minutes=30), sort_order=1)] if dt == 'Time Slot' else [Row(time_slot='S1', finished_quantity=case['quantity'])])
                row = metrics._slots('C', [Row(name='R')], case['day'])[0]
                self.assertEqual(case['visible'], row['is_visible'])
                self.assertEqual(case['current'], row['is_current'])
                self.assertEqual('07:30', row['start_time'])
                self.assertEqual('09:30', row['end_time'])

    def test_reported_slot_outside_default_list_retains_definition_and_order(self):
        def query(dt, **kw):
            if dt == 'Time Slot':
                slots = [Row(name='S2', slot_name='Ca 2', start_time='09:30:00', end_time='11:30:00', sort_order=2)]
                if 'name' in kw.get('filters', {}):
                    return [Row(name='S1', slot_name='Ca 1', start_time='07:30:00', end_time='09:30:00', sort_order=1)]
                return slots
            return [Row(time_slot='S1', finished_quantity=80), Row(time_slot='S2', finished_quantity=70)]
        frappe.get_all.side_effect = query
        rows = metrics._slots('C', [Row(name='R')], '2026-11-17')
        self.assertEqual(['S1', 'S2'], [r['time_slot'] for r in rows])
        self.assertEqual([80, 150], [r['cumulative_quantity'] for r in rows])

    def test_uqqc_counts_rework_pieces_not_defect_events(self):
        frappe.get_all.return_value = [Row(event_kind='pass', quantity=95), Row(event_kind='rework', quantity=5), Row(event_kind='defect', quantity=14)]
        total, defects, events = metrics._quality('L1', 'P', '2026-11-17', 'uqqc_input')
        self.assertEqual((100, 5, 1), (total, defects, events))
        filters = frappe.get_all.call_args.kwargs['filters']
        self.assertIn(['occurred_at', '>=', '2026-11-16 17:00:00.000000'], filters)
        self.assertIn(['occurred_at', '<', '2026-11-17 17:00:00.000000'], filters)

    def test_qc_clamps_whole_defect_total_like_dotnet_not_each_defect(self):
        events = [Row(device='QC1', event_type=t, quantity_delta=q, defect=d) for t,q,d in [('CumulativeAdd',100,None),('CumulativeSubtract',-10,None),('DefectAdd',5,'D1'),('DefectSubtract',-10,'D2'),('DefectAdd',3,'D1')]]
        events.append(Row(device='QC2', event_type='CumulativeAdd', quantity_delta=999))
        frappe.get_all.side_effect = lambda dt, **kw: events if dt == 'QC Inspection Event' else [Row(name='QC1', device_name=' 001qc1-test '),Row(name='QC2',device_name='002QC2')]
        self.assertEqual((90, 3, 2), metrics._quality('L1','P','2026-11-17','qc_input'))

    def test_quality_event_pagination_does_not_truncate_at_2000(self):
        frappe.get_all.side_effect = lambda dt, **kw: [Row(quantity=1)] * (2000 if kw['start'] == 0 else 3)
        self.assertEqual(2003, len(list(metrics._events('QC Inspection Event', ['quantity'], {}))))

    def test_latest_report_is_selected_once_not_summed_with_older_report(self):
        latest = Row(name=REFERENCE['latest_report'], product='P',production_plan='PLAN',daily_target_quantity=400,working_hours=8,worker_count=20,ironing_delivery_quantity=4)
        older = Row(name='old',product='P',production_plan='PLAN',daily_target_quantity=999,working_hours=9,worker_count=99)
        frappe.get_all.side_effect = lambda dt, **kw: [latest, older] if dt == 'Productivity Report' else []
        frappe.db.get_value.side_effect = lambda dt,*args,**kw: Row(line_code='315',line_name='C5X3',company='C') if dt == 'Production Line' else '217H006E'
        with patch.object(metrics,'_plan',return_value=None), patch.object(metrics,'_quality',return_value=(0,0,0)), patch.object(metrics,'_slots',return_value=[{'quantity':80}]) as slots:
            row = metrics.line_summary('L1','2026-11-17','qc_input')
        self.assertEqual(400,row['daily_target_quantity'])
        self.assertEqual(20,row['worker_count'])
        self.assertEqual(100,row['current_target_quantity'])
        self.assertEqual(1,row['report_count'])
        self.assertEqual(0,row['defect_rate_percent'])
        self.assertTrue(row['has_defect_rate'])
        self.assertEqual([latest], slots.call_args.args[1])

    def test_plan_selection_uses_effective_plan_before_report_link_like_dotnet(self):
        plans=[Row(name='00000000-0000-0000-0000-000000000020',line_start_date='2026-11-13',shipment_date='2026-11-22'),Row(name=REFERENCE['selected_plan'],line_start_date='2026-11-16',shipment_date='2026-11-23')]
        frappe.get_all.side_effect=lambda dt,**kw: [p for p in plans if p.name==kw['filters']['name']] if 'name' in kw.get('filters',{}) else plans
        self.assertEqual(REFERENCE['selected_plan'], metrics._plan('L1','2026-11-17',Row(production_plan=plans[0].name)).name)

    def test_group_slot_flags_are_or_combined_and_dates_and_leaders_preserved(self):
        seed=dict(line='L1',line_code='315',line_name='C5X3',product_code='P',report_count=1,finished_quantity=80,daily_target_quantity=400,current_target_quantity=100,planned_quantity=450,worker_count=20,working_hours=8,ironing_delivery_quantity=4,line_leader_name='Leader',technical_leader_name='Tech',qc_total_quantity=100,defect_quantity=5,defect_events=5,plan_start_date='2026-11-10',plan_shipment_date='2026-11-21',time_slots=[dict(time_slot='S',quantity=80,sort_order=1,start_time='07:30',is_visible=True,is_current=True)])
        second={**seed,'line':'L2','plan_start_date':'2026-11-11','plan_shipment_date':'2026-11-22','time_slots':[dict(seed['time_slots'][0],quantity=0,is_visible=False,is_current=False)]}
        with patch.object(metrics,'line_summary',side_effect=[seed,second]): row=metrics.panel_summary(['L1','L2'],'Group','2026-11-17','qc_input')
        self.assertTrue(row['time_slots'][0]['is_visible'])
        self.assertTrue(row['time_slots'][0]['is_current'])
        self.assertEqual('2026-11-10',row['plan_start_date'])
        self.assertEqual('2026-11-22',row['plan_shipment_date'])
        self.assertEqual('Leader',row['line_leader_name'])
        self.assertEqual(5,row['defect_rate_percent'])
        self.assertEqual(80,row['achievement_rate_percent'])

    def test_display_defaults_to_home_line_and_dual_keeps_left_right(self):
        current=dict(config={},home_line='L2',scope_lines=['L1','L2'])
        with patch.object(api,'profile',return_value=current),patch.object(api,'_settings',return_value=('qc_input',60)),patch.object(api,'panel_summary',side_effect=lambda lines,*args:{'source_lines':lines}):
            self.assertEqual([{'source_lines':['L2']}],api.display('DEV','2026-11-17')['lines'])
            current['config']=dict(display_mode='dual',left_line='L1',right_line='L2')
            self.assertEqual([{'source_lines':['L1']},{'source_lines':['L2']}],api.display('DEV','2026-11-17')['lines'])
            current['config']['right_line']='OUTSIDE'
            with self.assertRaises(PermissionError): api.display('DEV','2026-11-17')

    def test_full_line_payload_uses_raw_report_slots_plan_and_qc_events(self):
        plan=Row(name='PLAN',product='P',line_start_date='2026-11-10',shipment_date='2026-11-25',closed_production_date='2026-11-21',planned_quantity=450)
        report=Row(name='LATEST',product='P',production_plan='PLAN',daily_target_quantity=400,working_hours=8,worker_count=20,ironing_delivery_quantity=4)
        data={
            'Productivity Report':[report],
            'Productivity Production Plan':[plan],
            'Time Slot':[Row(name='S1',slot_name='Ca 1',start_time='7:30:00',end_time='9:30:00',sort_order=1),Row(name='S2',slot_name='Ca 2',start_time='9:30:00',end_time='11:30:00',sort_order=2)],
            'Productivity Report Time Slot':[Row(time_slot='S1',finished_quantity=80),Row(time_slot='S2',finished_quantity=0)],
            'Productivity Line Info':[Row(line_leader_name='Leader',technical_leader_name='Tech')],
            'QC Inspection Event':[Row(device='QC1',event_type='CumulativeAdd',quantity_delta=100),Row(device='QC1',event_type='DefectAdd',quantity_delta=5,defect='D')],
            'Factory Device':[Row(name='QC1',device_name='001QC1')],
        }
        frappe.get_all.side_effect=lambda dt,**kw:data[dt]
        frappe.db.get_value.side_effect=lambda dt,*a,**kw:Row(line_code='315',line_name='C5X3',company='C') if dt=='Production Line' else '216F012B'
        row=metrics.line_summary('L1','2026-11-17','qc_input')
        self.assertEqual((400,100,80,80,5),(row['daily_target_quantity'],row['current_target_quantity'],row['finished_quantity'],row['achievement_rate_percent'],row['defect_rate_percent']))
        self.assertEqual('2026-11-21',row['plan_shipment_date'])
        self.assertEqual([80,80],[x['cumulative_quantity'] for x in row['time_slots']])
        self.assertEqual([False,True],[x['is_current'] for x in row['time_slots']])

    def test_group_with_mixed_products_suppresses_combined_kpis_like_dotnet(self):
        seed=dict(line='L1',line_code='315',line_name='C5X3',product_code='P',report_count=1,finished_quantity=80,daily_target_quantity=400,current_target_quantity=100,planned_quantity=450,worker_count=20,working_hours=8,ironing_delivery_quantity=4,line_leader_name='Leader',technical_leader_name='Tech',qc_total_quantity=100,defect_quantity=5,defect_events=5,plan_start_date='2026-11-10',plan_shipment_date='2026-11-21',time_slots=[])
        with patch.object(metrics,'line_summary',side_effect=[seed,dict(seed,product_code='OTHER')]): row=metrics.panel_summary(['L1','L2'],'Group','2026-11-17','qc_input')
        self.assertTrue(row['mixed_products'])
        self.assertFalse(row['has_defect_rate'])
        self.assertEqual(0,row['finished_quantity'])
        self.assertEqual(0,row['daily_target_quantity'])
        self.assertEqual([],row['time_slots'])


if __name__ == '__main__':
    unittest.main()
