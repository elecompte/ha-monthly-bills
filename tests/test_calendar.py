"""Calendar rules and entity wiring, using HA doubles for the entity tests."""
import ast
from dataclasses import dataclass
from datetime import date, datetime
import importlib
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
import unittest
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1] / "custom_components/monthly_bills"
PACKAGE = "monthly_bills_calendar_test"
package = ModuleType(PACKAGE)
package.__path__ = [str(ROOT)]
sys.modules[PACKAGE] = package
calendar_model = importlib.import_module(f"{PACKAGE}.calendar_model")
model = importlib.import_module(f"{PACKAGE}.model")
LOCAL = ZoneInfo("America/New_York")


def bill(name="Rent", due="2026-11-01", amount=1400):
    return model.migrate_bill({
        "name": name, "due_date": due, "cost": amount, "due_day": date.fromisoformat(due).day,
        "paid": False, "paid_on": None, "category": "Housing", "history": [],
    })


def local(year, month, day, hour=0):
    return datetime(year, month, day, hour, tzinfo=LOCAL)


class CalendarRulesTests(unittest.TestCase):
    def test_title_dates_description_and_stable_uid(self):
        events = calendar_model.bill_events({"rent": bill()}, date(2026,10,12))
        event = events[0]
        self.assertEqual(event["start"], date(2026,11,1))
        self.assertEqual(event["end"], date(2026,11,2))
        self.assertEqual(event["summary"], "Rent — $1,400.00")
        self.assertIn("Status: Upcoming", event["description"])
        changed = calendar_model.bill_events({"rent": bill(amount=1500)}, date(2026,10,12))[0]
        self.assertEqual(event["uid"],changed["uid"])

    def test_multiple_bills_same_day_sort_and_distinct_uids(self):
        events=calendar_model.bill_events({
            "rent":bill(), "electric":bill("Electric"), "internet":bill("Internet","2026-10-30")
        },date(2026,10,12))
        self.assertEqual([e["summary"].split(" — ")[0] for e in events],["Internet","Electric","Rent"])
        self.assertEqual(len({e["uid"] for e in events}),3)

    def test_exclusive_range_boundaries(self):
        events=calendar_model.bill_events({"rent":bill()},date(2026,10,12))
        self.assertEqual(calendar_model.events_between(events,local(2026,10,1),local(2026,11,1)),[])
        self.assertEqual(calendar_model.events_between(events,local(2026,11,2),local(2026,12,1)),[])
        self.assertEqual(len(calendar_model.events_between(events,local(2026,11,1),local(2026,11,2))),1)
        self.assertEqual(len(calendar_model.events_between(events,local(2026,11,1,12),local(2026,11,1,13))),1)

    def test_empty_calendar_and_empty_range(self):
        self.assertEqual(calendar_model.bill_events({},date(2026,10,12)),[])
        self.assertIsNone(calendar_model.current_or_next([],date(2026,10,12)))
        events=calendar_model.bill_events({"rent":bill()},date(2026,10,12))
        self.assertEqual(calendar_model.events_between(events,local(2026,11,1),local(2026,11,1)),[])

    def test_dst_all_day_event_overlaps_full_local_day(self):
        events=calendar_model.bill_events({"rent":bill()},date(2026,10,12))
        # November 1 is a 25-hour day in New York in 2026.
        self.assertEqual(len(calendar_model.events_between(events,local(2026,11,1),local(2026,11,2))),1)

    def test_overdue_is_returned_in_past_range_not_next_event(self):
        events=calendar_model.bill_events({"rent":bill(due="2026-10-01")},date(2026,10,12))
        self.assertIn("Status: Past Due",events[0]["description"])
        self.assertIsNone(calendar_model.current_or_next(events,date(2026,10,12)))
        self.assertEqual(len(calendar_model.events_between(events,local(2026,10,1),local(2026,10,2))),1)

    def test_due_today_is_current_event(self):
        events=calendar_model.bill_events({"rent":bill()},date(2026,11,1))
        self.assertEqual(calendar_model.current_or_next(events,date(2026,11,1)),events[0])
        self.assertIn("Status: Due Today",events[0]["description"])

    def test_payment_moves_event_and_next_cycle_is_unpaid(self):
        before=bill(due="2026-10-01")
        after=model.record_payment(before,date(2026,10,1))
        events=calendar_model.bill_events({"rent":after},date(2026,10,12))
        self.assertEqual(len(events),1)
        self.assertEqual(events[0]["start"],date(2026,11,1))
        self.assertIn("Status: Upcoming",events[0]["description"])
        self.assertIn("Last payment: 2026-10-01",events[0]["description"])
        self.assertTrue(after["paid"])

    def test_disabled_auto_advance_paid_date_is_retained(self):
        b=bill(due="2026-10-01");b["auto_advance_due_date"]=False
        b=model.record_payment(b,date(2026,10,1))
        events=calendar_model.bill_events({"rent":b},date(2026,10,12))
        self.assertEqual(events[0]["start"],date(2026,10,1))
        self.assertIn("Status: Paid",events[0]["description"])


@dataclass
class EventDouble:
    start: date
    end: date
    summary: str
    description: str
    uid: str


class EntityDouble:
    async def async_added_to_hass(self):
        self.base_added=True
    def async_on_remove(self, unsubscribe):
        self.unsubscribe=unsubscribe
    def async_write_ha_state(self):
        self.writes=getattr(self,"writes",0)+1
    def async_update_event_listeners(self):
        self.notifications=getattr(self,"notifications",0)+1


clock=SimpleNamespace(today=date(2026,10,12))
subscriptions=[]
def connect(hass, signal, listener):
    subscriptions.append(listener)
    return lambda: subscriptions.remove(listener)

namespace=dict(
    datetime=datetime,CalendarEntity=EntityDouble,CalendarEvent=EventDouble,
    callback=lambda f:f,
    dt_util=SimpleNamespace(
        now=lambda:SimpleNamespace(date=lambda:clock.today),
        as_local=lambda value:value.astimezone(LOCAL)),
    async_dispatcher_connect=connect,SIGNAL_CHANGED="changed",
    **{name:getattr(calendar_model,name) for name in ["bill_events","current_or_next","events_between"]})
tree=ast.parse((ROOT/"calendar.py").read_text())
nodes=[node for node in tree.body if isinstance(node,ast.ClassDef)]
exec(compile(ast.Module(body=nodes,type_ignores=[]),str(ROOT/"calendar.py"),"exec"),namespace)
Calendar=namespace["MonthlyBillsCalendar"]


class CalendarEntityTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        clock.today=date(2026,10,12)
        self.manager=SimpleNamespace(bills={"rent":bill()})
        self.calendar=Calendar(self.manager)
        self.calendar.hass=object()

    async def test_entity_next_event_and_utc_range_conversion(self):
        self.assertEqual(self.calendar.event.summary,"Rent — $1,400.00")
        start=datetime(2026,11,1,4,tzinfo=ZoneInfo("UTC"))
        end=datetime(2026,11,2,5,tzinfo=ZoneInfo("UTC"))
        events=await self.calendar.async_get_events(None,start,end)
        self.assertEqual(len(events),1)
        self.assertIsInstance(events[0].start,date)
        self.assertEqual(events[0].end,date(2026,11,2))

    async def test_non_next_event_edit_notifies_and_delete_removes_event(self):
        await self.calendar.async_added_to_hass()
        self.manager.bills["internet"]=bill("Internet","2026-11-15",100)
        self.calendar._bills_changed()
        self.assertEqual(self.calendar.notifications,1)
        events=await self.calendar.async_get_events(None,local(2026,11,1),local(2026,12,1))
        self.assertEqual(len(events),2)
        self.manager.bills["internet"]["due_date"]="2026-12-15"
        self.calendar._bills_changed()
        events=await self.calendar.async_get_events(None,local(2026,11,1),local(2026,12,1))
        self.assertEqual(len(events),1)
        del self.manager.bills["rent"]
        self.calendar._bills_changed()
        self.assertEqual(self.calendar.event.start,date(2026,12,15))
        self.assertEqual(self.calendar.notifications,3)
        self.calendar.unsubscribe()
        self.assertNotIn(self.calendar._bills_changed,subscriptions)
