"""Monthly Bills: editable local bill storage and actions."""

import asyncio
from datetime import date as datetime_date
import logging
import re

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.util import dt as dt_util
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_time_change
from homeassistant.helpers.storage import Store

from .const import DOMAIN, SIGNAL_CHANGED, STORE_KEY, STORE_VERSION
from .frontend import async_register_frontend
from .model import checked_threshold, correct_last_payment_date, migrate_bill, record_payment, refresh_bill, reopen_bill, roll_bill

_LOGGER = logging.getLogger(__name__)
PLATFORMS = ["sensor", "number", "date", "switch", "text", "calendar"]
COST = vol.All(vol.Coerce(float), vol.Range(min=0, max=100000000))
DATE = vol.Match(r"^\d{4}-\d{2}-\d{2}$")
THRESHOLD = checked_threshold
ID = vol.Match(r"^[a-z0-9_]+$")

ADD_SCHEMA = vol.Schema({
    vol.Required("name"): vol.All(str, vol.Length(min=1, max=100)),
    vol.Required("cost"): COST,
    vol.Required("due_date"): DATE,
    vol.Optional("category", default="Other"): str,
    vol.Optional("auto_advance_due_date", default=True): bool,
    vol.Optional("upcoming_threshold_days", default=7): THRESHOLD,
})
UPDATE_SCHEMA = vol.Schema({
    vol.Required("bill_id"): ID,
    vol.Optional("name"): vol.All(str, vol.Length(min=1, max=100)),
    vol.Optional("cost"): COST,
    vol.Optional("due_date"): DATE,
    vol.Optional("category"): str,
    vol.Optional("auto_advance_due_date"): bool,
    vol.Optional("upcoming_threshold_days"): THRESHOLD,
})
TARGET_SCHEMA = vol.Schema({vol.Required("bill_id"): ID})
PAYMENT_DATE_SCHEMA = vol.Schema({
    vol.Required("bill_id"): ID,
    vol.Required("paid_on"): DATE,
})


def checked_date(value: str | datetime_date) -> datetime_date:
    """Accept the UI's date value and the ISO string used by HA actions."""
    try:
        if isinstance(value, datetime_date):
            return value
        return datetime_date.fromisoformat(str(value))
    except (ValueError, TypeError) as err:
        raise HomeAssistantError("due_date must be a real date (YYYY-MM-DD)") from err


class BillManager:
    """Own and persist all bills for the single configuration entry."""

    def __init__(self, hass: HomeAssistant):
        self.hass = hass
        self.store = Store(hass, STORE_VERSION, STORE_KEY)
        self.bills: dict[str, dict] = {}
        self.lock = asyncio.Lock()

    async def load(self):
        data = await self.store.async_load() or {}
        old_bills = data.get("bills", {})
        self.bills = {key: migrate_bill(bill) for key, bill in old_bills.items()}
        if self.bills != old_bills:
            await self.save()

    def notify(self):
        async_dispatcher_send(self.hass, SIGNAL_CHANGED)

    async def save(self):
        await self.store.async_save({"bills": self.bills})
        self.notify()

    async def add(self, data: dict):
        due = checked_date(data["due_date"])
        name = str(data["name"]).strip()
        if not name:
            raise HomeAssistantError("Bill name cannot be blank")
        amount = round(float(data["cost"]), 2)
        if not 0 <= amount <= 100000000:
            raise HomeAssistantError("Bill amount is out of range")
        category = str(data.get("category") or "Other").strip() or "Other"
        base = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_") or "bill"
        async with self.lock:
            bill_id = base
            index = 2
            while bill_id in self.bills:
                bill_id = f"{base}_{index}"
                index += 1
            self.bills[bill_id] = {
                "id": bill_id,
                "name": name,
                "cost": amount,
                "due_date": due.isoformat(),
                "due_day": due.day,
                "category": category,
                "paid": False,
                "paid_on": None,
                "history": [],
                "auto_advance_due_date": bool(data.get("auto_advance_due_date", True)),
                "upcoming_threshold_days": THRESHOLD(data.get("upcoming_threshold_days", 7)),
                "last_paid_on": None,
                "last_paid_due_date": None,
                "auto_advanced": False,
            }
            await self.save()
        return bill_id

    def get(self, bill_id):
        if bill_id not in self.bills:
            raise HomeAssistantError(f"Unknown bill_id: {bill_id}")
        return self.bills[bill_id]

    async def update(self, data: dict):
        async with self.lock:
            # Validate on a copy so rejected edits cannot partially mutate storage.
            bill = dict(self.get(data["bill_id"]))
            for field in ("name", "category"):
                if field in data:
                    bill[field] = str(data[field]).strip()
            if not bill["name"]:
                raise HomeAssistantError("Bill name cannot be blank")
            if "cost" in data:
                bill["cost"] = round(COST(data["cost"]), 2)
            if "due_date" in data:
                due = checked_date(data["due_date"])
                if due.isoformat() != bill["due_date"]:
                    bill = reopen_bill(bill)
                    bill["due_date"] = due.isoformat()
                    bill["due_day"] = due.day
            if "auto_advance_due_date" in data:
                bill["auto_advance_due_date"] = bool(data["auto_advance_due_date"])
            if "upcoming_threshold_days" in data:
                bill["upcoming_threshold_days"] = THRESHOLD(data["upcoming_threshold_days"])
            self.bills[data["bill_id"]] = refresh_bill(bill, dt_util.now().date())
            await self.save()

    async def set_paid(self, bill_id: str, paid: bool, explicit: bool = False):
        async with self.lock:
            bill = self.get(bill_id)
            updated = record_payment(bill, dt_util.now().date(), explicit) if paid else reopen_bill(bill)
            if updated != bill:
                self.bills[bill_id] = updated
                await self.save()

    async def rollover(self, bill_id: str):
        async with self.lock:
            bill = refresh_bill(self.get(bill_id), dt_util.now().date())
            try:
                self.bills[bill_id] = roll_bill(bill)
            except ValueError as err:
                raise HomeAssistantError(str(err)) from err
            await self.save()

    async def correct_payment_date(self, bill_id: str, paid_on: str | datetime_date):
        """Edit a recorded payment date, preserving due date and status."""
        paid_date = checked_date(paid_on)
        if paid_date > dt_util.now().date():
            raise HomeAssistantError("Payment date cannot be in the future")
        async with self.lock:
            bill = self.get(bill_id)
            try:
                updated = correct_last_payment_date(bill, paid_date)
            except ValueError as err:
                raise HomeAssistantError(str(err)) from err
            if updated != bill:
                self.bills[bill_id] = updated
                await self.save()

    async def delete(self, bill_id: str):
        async with self.lock:
            self.get(bill_id)
            del self.bills[bill_id]
            await self.save()

    async def daily_tick(self):
        """Refresh acknowledgement at the threshold; never advance dates here."""
        async with self.lock:
            today = dt_util.now().date()
            updated = {key: refresh_bill(bill, today) for key, bill in self.bills.items()}
            if updated != self.bills:
                self.bills = updated
                await self.save()
            else:
                self.notify()


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Register actions once, including when no config entry exists yet."""
    hass.data.setdefault(DOMAIN, {})
    await async_register_frontend(hass)

    def manager() -> BillManager:
        managers = hass.data[DOMAIN]
        if not managers:
            raise HomeAssistantError("First add Monthly Bills in Settings > Devices & Services.")
        return next(iter(managers.values()))

    async def add_bill(call: ServiceCall):
        await manager().add(dict(call.data))

    async def update_bill(call: ServiceCall):
        await manager().update(dict(call.data))

    async def mark_paid(call: ServiceCall):
        await manager().set_paid(call.data["bill_id"], True)

    async def pay_next_cycle(call: ServiceCall):
        await manager().set_paid(call.data["bill_id"], True, explicit=True)

    async def mark_unpaid(call: ServiceCall):
        await manager().set_paid(call.data["bill_id"], False)

    async def update_last_payment_date(call: ServiceCall):
        await manager().correct_payment_date(call.data["bill_id"], call.data["paid_on"])

    async def rollover(call: ServiceCall):
        await manager().rollover(call.data["bill_id"])

    async def delete_bill(call: ServiceCall):
        await manager().delete(call.data["bill_id"])

    hass.services.async_register(DOMAIN, "add_bill", add_bill, schema=ADD_SCHEMA)
    hass.services.async_register(DOMAIN, "update_bill", update_bill, schema=UPDATE_SCHEMA)
    hass.services.async_register(DOMAIN, "mark_paid", mark_paid, schema=TARGET_SCHEMA)
    hass.services.async_register(DOMAIN, "pay_next_cycle", pay_next_cycle, schema=TARGET_SCHEMA)
    hass.services.async_register(DOMAIN, "mark_unpaid", mark_unpaid, schema=TARGET_SCHEMA)
    hass.services.async_register(DOMAIN, "update_last_payment_date", update_last_payment_date, schema=PAYMENT_DATE_SCHEMA)
    hass.services.async_register(DOMAIN, "rollover", rollover, schema=TARGET_SCHEMA)
    hass.services.async_register(DOMAIN, "delete_bill", delete_bill, schema=TARGET_SCHEMA)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    bills = BillManager(hass)
    await bills.load()
    hass.data[DOMAIN][entry.entry_id] = bills
    await bills.daily_tick()  # Catch up after restarts
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    @callback
    def midnight_tick(_now):
        hass.async_create_task(bills.daily_tick())

    entry.async_on_unload(async_track_time_change(hass, midnight_tick, hour=0, minute=0, second=5))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    if await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id, None)
        return True
    return False
