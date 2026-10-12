"""Run with python3 -m unittest discover -s tests -v (no HA required)."""
import ast
import asyncio
import importlib.util
from datetime import date
from pathlib import Path
from types import SimpleNamespace
import unittest

ROOT = Path(__file__).resolve().parents[1] / 'custom_components/monthly_bills'
spec = importlib.util.spec_from_file_location('bill_model', ROOT / 'model.py')
model = importlib.util.module_from_spec(spec)
spec.loader.exec_module(model)


def bill(due='2026-10-01', paid=False, auto=True, threshold=7):
    return model.migrate_bill(dict(id='rent', name='Rent', cost=1400.0,
        due_date=due, due_day=date.fromisoformat(due).day, category='Other',
        paid=paid, paid_on='2026-09-30' if paid else None, history=[],
        auto_advance_due_date=auto, upcoming_threshold_days=threshold))


class BillingTests(unittest.TestCase):
    def test_payment_and_threshold_boundaries(self):
        b = model.record_payment(bill(), date(2026, 10, 1))
        self.assertEqual(b['due_date'], '2026-11-01')
        self.assertEqual(b['history'][0]['due_date'], '2026-10-01')
        for day, status in [(date(2026,10,24),'Paid'), (date(2026,10,25),'Upcoming'),
                            (date(2026,11,1),'Due Today'), (date(2026,11,2),'Past Due')]:
            self.assertEqual(model.status_for(b,day),status)
        b = model.refresh_bill(b,date(2026,10,25))
        self.assertFalse(b['paid'])
        self.assertEqual(b['last_paid_on'],'2026-10-01')
        self.assertEqual(len(b['history']),1)

    def test_duplicate_paid_is_noop(self):
        b = model.record_payment(bill(),date(2026,10,1))
        self.assertEqual(model.record_payment(b,date(2026,10,2)),b)

    def test_pay_early(self):
        b = model.record_payment(bill(),date(2026,10,1))
        b = model.record_payment(b,date(2026,10,20),explicit=True)
        self.assertEqual(b['due_date'],'2026-12-01')
        self.assertEqual(b['last_paid_due_date'],'2026-11-01')
        self.assertEqual(model.status_for(b,date(2026,11,23)),'Paid')
        self.assertEqual(model.status_for(b,date(2026,11,24)),'Upcoming')

    def test_disabled_remains_paid_and_no_date_change(self):
        b = model.record_payment(bill(auto=False),date(2026,10,1))
        self.assertEqual(b['due_date'],'2026-10-01')
        self.assertEqual(model.status_for(b,date(2027,1,1)),'Paid')
        self.assertEqual(model.refresh_bill(b,date(2027,1,1)),b)
        self.assertEqual(model.record_payment(b,date(2026,10,2),explicit=True),b)

    def test_threshold_zero_and_thirty(self):
        b = model.record_payment(bill(threshold=0),date(2026,10,1))
        self.assertEqual(model.status_for(b,date(2026,10,31)),'Paid')
        self.assertEqual(model.status_for(b,date(2026,11,1)),'Due Today')
        b = model.record_payment(bill(threshold=30),date(2026,10,1))
        self.assertEqual(model.status_for(b,date(2026,10,1)),'Paid')
        self.assertEqual(model.status_for(b,date(2026,10,2)),'Upcoming')

    def test_short_months_leap_year_and_year_boundary(self):
        for year, feb in [(2026,'2026-02-28'),(2028,'2028-02-29')]:
            b=bill(f'{year}-01-31')
            b=model.record_payment(b,date(year,1,31))
            self.assertEqual(b['due_date'],feb)
            b=model.record_payment(b,date(year,2,28),explicit=True)
            self.assertEqual(b['due_date'],f'{year}-03-31')
        self.assertEqual(model.next_due_date(bill('2026-12-31')),'2027-01-31')

    def test_late_payment_advances_only_one_cycle(self):
        b=model.record_payment(bill(),date(2026,12,10))
        self.assertEqual(b['due_date'],'2026-11-01')
        self.assertEqual(model.status_for(b,date(2026,12,10)),'Past Due')
        self.assertEqual(len(b['history']),1)
        self.assertEqual(model.record_payment(b,date(2026,12,10)),b)

    def test_threshold_validation(self):
        self.assertEqual(model.checked_threshold(7.0),7)
        for value in [-1,31,7.5,float('nan'),float('inf')]:
            with self.assertRaises(ValueError): model.checked_threshold(value)

    def test_migration_preserves_old_fields_and_is_idempotent(self):
        b=bill(paid=True)
        old={k:v for k,v in b.items() if k not in ['auto_advance_due_date','upcoming_threshold_days','last_paid_on','last_paid_due_date','auto_advanced']}
        migrated=model.migrate_bill(old)
        for key,value in old.items(): self.assertEqual(migrated[key],value)
        self.assertEqual(model.refresh_bill(migrated,date(2027,1,1)),migrated)
        self.assertEqual(model.migrate_bill(migrated),migrated)

    def test_rollover_prevents_double_advance(self):
        b=model.record_payment(bill(),date(2026,10,1))
        with self.assertRaises(ValueError): model.roll_bill(b)
        with self.assertRaises(ValueError): model.roll_bill(bill())
        b=model.record_payment(bill(auto=False),date(2026,10,1))
        b=model.roll_bill(b)
        self.assertEqual(b['due_date'],'2026-11-01')
        self.assertFalse(b['paid'])
        self.assertEqual(len(b['history']),1)

    def test_reopening_preserves_history_and_next_date(self):
        b=model.record_payment(bill(),date(2026,10,1))
        reopened=model.reopen_bill(b)
        self.assertEqual(reopened['due_date'],'2026-11-01')
        self.assertEqual(reopened['history'],b['history'])
        self.assertFalse(reopened['paid'])

    def test_history_is_bounded(self):
        b=bill('2024-01-01')
        for _ in range(30): b=model.record_payment(b,date.fromisoformat(b['due_date']),explicit=True)
        self.assertEqual(len(b['history']),24)


# Execute the actual manager class with in-memory HA storage/time/dispatcher
# doubles. This covers persistence and serialization without a HA installation.
class Store:
    def __init__(self,*args): self.data=None; self.writes=0
    async def async_load(self): return self.data
    async def async_save(self,data):
        import copy
        self.data=copy.deepcopy(data); self.writes+=1

clock=SimpleNamespace(today=date(2026,10,1))
def threshold(value):
    value=float(value)
    if not value.is_integer() or not 0 <= value <= 30: raise ValueError('invalid threshold')
    return int(value)

tree=ast.parse((ROOT/'__init__.py').read_text())
manager_nodes=[node for node in tree.body if isinstance(node,(ast.ClassDef,ast.FunctionDef)) and node.name in ('BillManager','checked_date')]
namespace=dict(asyncio=asyncio,datetime_date=date,re=__import__('re'),HomeAssistant=object,
    HomeAssistantError=ValueError,Store=Store,STORE_VERSION=1,STORE_KEY='monthly_bills.data',
    SIGNAL_CHANGED='changed',async_dispatcher_send=lambda *args: None,
    dt_util=SimpleNamespace(now=lambda: SimpleNamespace(date=lambda: clock.today)),
    THRESHOLD=threshold,COST=lambda value: float(value),
    **{name:getattr(model,name) for name in ['correct_last_payment_date','migrate_bill','record_payment','refresh_bill','reopen_bill','roll_bill']})
exec(compile(ast.Module(body=manager_nodes,type_ignores=[]),str(ROOT/'__init__.py'),'exec'),namespace)
BillManager=namespace['BillManager']

class ManagerTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        clock.today=date(2026,10,1)
        self.manager=BillManager(object())
        await self.manager.add(dict(name='Rent',cost=1400,due_date='2026-10-01'))

    async def test_concurrent_payment_calls(self):
        await asyncio.gather(*(self.manager.set_paid('rent',True) for _ in range(10)))
        self.assertEqual(self.manager.bills['rent']['due_date'],'2026-11-01')
        self.assertEqual(len(self.manager.bills['rent']['history']),1)

    async def test_restart_refresh_does_not_advance(self):
        await self.manager.set_paid('rent',True)
        clock.today=date(2026,11,2)
        restarted=BillManager(object()); restarted.store=self.manager.store
        await restarted.load(); await restarted.daily_tick()
        self.assertEqual(restarted.bills['rent']['due_date'],'2026-11-01')
        self.assertEqual(model.status_for(restarted.bills['rent'],clock.today),'Past Due')
        self.assertEqual(restarted.bills['rent']['last_paid_on'],'2026-10-01')

    async def test_threshold_change_refreshes_immediately(self):
        await self.manager.set_paid('rent',True)
        clock.today=date(2026,10,20)
        await self.manager.update(dict(bill_id='rent',upcoming_threshold_days=12))
        self.assertFalse(self.manager.bills['rent']['paid'])
        self.assertEqual(self.manager.store.data['bills']['rent']['upcoming_threshold_days'],12)

    async def test_disabled_and_manual_date_reopen(self):
        await self.manager.update(dict(bill_id='rent',auto_advance_due_date=False))
        await self.manager.set_paid('rent',True)
        clock.today=date(2026,12,1); await self.manager.daily_tick()
        self.assertTrue(self.manager.bills['rent']['paid'])
        await self.manager.update(dict(bill_id='rent',due_date='2027-01-15'))
        self.assertFalse(self.manager.bills['rent']['paid'])
        self.assertEqual(self.manager.bills['rent']['due_day'],15)

    async def test_invalid_edit_does_not_partially_mutate(self):
        import copy
        old=copy.deepcopy(self.manager.bills)
        with self.assertRaises(ValueError):
            await self.manager.update(dict(bill_id='rent',name='New',due_date='2026-02-30'))
        self.assertEqual(self.manager.bills,old)

    async def test_settings_and_last_paid_survive_restart(self):
        await self.manager.update(dict(bill_id='rent',auto_advance_due_date=False,upcoming_threshold_days=10))
        await self.manager.set_paid('rent',True)
        restarted=BillManager(object()); restarted.store=self.manager.store; await restarted.load()
        self.assertEqual(restarted.bills,self.manager.bills)

    async def test_correct_archived_latest_payment(self):
        import copy
        await self.manager.set_paid('rent',True)
        clock.today=date(2026,10,12)
        before=copy.deepcopy(self.manager.bills['rent'])
        await self.manager.correct_payment_date('rent','2026-09-30')
        after=self.manager.bills['rent']
        self.assertEqual(after['last_paid_on'],'2026-09-30')
        self.assertEqual(after['paid_on'],'2026-09-30')
        self.assertEqual(after['history'][-1]['paid_on'],'2026-09-30')
        for field in ['due_date','due_day','last_paid_due_date','paid','auto_advanced','cost','last_payment_recorded_on']:
            self.assertEqual(after[field],before[field])
        restarted=BillManager(object()); restarted.store=self.manager.store
        await restarted.load()
        self.assertEqual(restarted.bills,self.manager.bills)

    async def test_correct_after_upcoming_preserves_unpaid(self):
        await self.manager.set_paid('rent',True)
        clock.today=date(2026,10,25); await self.manager.daily_tick()
        await self.manager.correct_payment_date('rent','2026-09-30')
        after=self.manager.bills['rent']
        self.assertFalse(after['paid'])
        self.assertIsNone(after['paid_on'])
        self.assertEqual(after['due_date'],'2026-11-01')
        self.assertEqual(model.status_for(after,clock.today),'Upcoming')
        self.assertEqual(after['history'][-1]['paid_on'],'2026-09-30')

    async def test_correction_does_not_break_same_day_retry(self):
        clock.today=date(2026,12,10)
        await self.manager.set_paid('rent',True)
        await self.manager.correct_payment_date('rent','2026-12-01')
        await self.manager.set_paid('rent',True)
        self.assertEqual(self.manager.bills['rent']['due_date'],'2026-11-01')
        self.assertEqual(len(self.manager.bills['rent']['history']),1)

    async def test_current_unarchived_payment_corrected_before_rollover(self):
        await self.manager.update(dict(bill_id='rent',auto_advance_due_date=False))
        await self.manager.set_paid('rent',True)
        await self.manager.correct_payment_date('rent','2026-09-30')
        self.assertEqual(self.manager.bills['rent']['history'],[])
        await self.manager.rollover('rent')
        self.assertEqual(self.manager.bills['rent']['history'][-1]['paid_on'],'2026-09-30')

    async def test_correction_only_changes_latest_history(self):
        await self.manager.set_paid('rent',True)
        clock.today=date(2026,10,12)
        await self.manager.set_paid('rent',True,explicit=True)
        await self.manager.correct_payment_date('rent','2026-10-10')
        history=self.manager.bills['rent']['history']
        self.assertEqual(history[0]['paid_on'],'2026-10-01')
        self.assertEqual(history[1]['paid_on'],'2026-10-10')
        self.assertEqual(history[1]['due_date'],'2026-11-01')
        self.assertEqual(self.manager.bills['rent']['due_date'],'2026-12-01')

    async def test_current_payment_does_not_modify_older_archived_payment(self):
        await self.manager.set_paid('rent',True)
        await self.manager.update(dict(bill_id='rent',auto_advance_due_date=False))
        clock.today=date(2026,10,25); await self.manager.daily_tick()
        await self.manager.set_paid('rent',True)
        await self.manager.correct_payment_date('rent','2026-10-20')
        after=self.manager.bills['rent']
        self.assertEqual(after['paid_on'],'2026-10-20')
        self.assertEqual(after['history'][0]['paid_on'],'2026-10-01')

    async def test_invalid_correction_leaves_bill_untouched(self):
        import copy
        before=copy.deepcopy(self.manager.bills)
        for value in ['2026-02-30','2026-10-02','2026-09-30']:
            with self.assertRaises(ValueError):
                await self.manager.correct_payment_date('rent',value)
            self.assertEqual(self.manager.bills,before)

    async def test_legacy_paid_payment_correction(self):
        self.manager.bills['rent']=model.migrate_bill(dict(
            id='rent',name='Rent',cost=1400,due_date='2026-10-01',due_day=1,
            category='Other',paid=True,paid_on='2026-10-01',history=[]))
        await self.manager.correct_payment_date('rent','2026-09-30')
        self.assertEqual(self.manager.bills['rent']['paid_on'],'2026-09-30')
        self.assertEqual(self.manager.bills['rent']['due_date'],'2026-10-01')

    async def test_stale_cycle_marker_does_not_block_latest_history_correction(self):
        import copy
        await self.manager.set_paid('rent',True)
        self.manager.bills['rent']['last_paid_due_date']='2026-09-01'
        before=copy.deepcopy(self.manager.bills['rent'])
        await self.manager.correct_payment_date('rent','2026-09-30')
        after=self.manager.bills['rent']
        self.assertEqual(after['history'][-1]['paid_on'],'2026-09-30')
        self.assertEqual(after['last_paid_on'],'2026-09-30')
        self.assertEqual(after['paid_on'],'2026-09-30')
        for key in ['due_date','due_day','paid','auto_advanced','last_paid_due_date','last_payment_recorded_on']:
            self.assertEqual(after[key],before[key])

    async def test_stale_cycle_marker_after_upcoming_keeps_bill_unpaid(self):
        await self.manager.set_paid('rent',True)
        self.manager.bills['rent']['last_paid_due_date']='2026-09-01'
        clock.today=date(2026,10,25)
        await self.manager.daily_tick()
        await self.manager.correct_payment_date('rent','2026-09-30')
        after=self.manager.bills['rent']
        self.assertIsNone(after['paid_on'])
        self.assertFalse(after['paid'])
        self.assertEqual(after['due_date'],'2026-11-01')
        self.assertEqual(after['last_paid_due_date'],'2026-09-01')
        self.assertEqual(after['history'][-1]['paid_on'],'2026-09-30')

if __name__=='__main__': unittest.main()
