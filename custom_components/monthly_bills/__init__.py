"""Monthly Bills: editable local bill storage and actions."""

import asyncio
from datetime import date
import logging
import re
import datetime as dt

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.util import dt as dt_util
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_time_change
from homeassistant.helpers.storage import Store

from .const import DOMAIN, SIGNAL_CHANGED, STORE_KEY, STORE_VERSION
from .model import roll_bill, status_for

_LOGGER = logging.getLogger(__name__)
PLATFORMS = ["sensor", "number", "date", "switch", "text"]
COST = vol.All(vol.Coerce(float), vol.Range(min=0, max=100000000))
DATE = vol.Match(r"^\d{4}-\d{2}-\d{2}$")
ID = vol.Match(r"^[a-z0-9_]+$")

ADD_SCHEMA = vol.Schema({
    vol.Required("name"): vol.All(str, vol.Length(min=1, max=100)),
    vol.Required("cost"): COST,
    vol.Required("due_date"): DATE,
    vol.Optional("category", default="Other"): str,
})
UPDATE_SCHEMA = vol.Schema({
    vol.Required("bill_id"): ID,
    vol.Optional("name"): vol.All(str, vol.Length(min=1, max=100)),
    vol.Optional("cost"): COST,
    vol.Optional("due_date"): DATE,
    vol.Optional("category"): str,
})
TARGET_SCHEMA = vol.Schema({vol.Required("bill_id"): ID})


def checked_date(value):
    """Validate and normalize a date to YYYY-MM-DD."""
    try:
        if isinstance(value, dt.datetime):
            return value.date().isoformat()

        if isinstance(value, dt.date):
            return value.isoformat()

        if isinstance(value, str):
            return dt.date.fromisoformat(value).isoformat()

    except (ValueError, TypeError) as err:
        raise HomeAssistantError(
            "due_date must be a real date (YYYY-MM-DD)"
        ) from err

    raise HomeAssistantError(
        "due_date must be a real date (YYYY-MM-DD)"
    )


class BillManager:
    """Own and persist all bills for the single configuration entry."""

    def __init__(self, hass: HomeAssistant):
        self.hass = hass
        self.store = Store(hass, STORE_VERSION, STORE_KEY)
        self.bills: dict[str, dict] = {}
        self.lock = asyncio.Lock()

    async def load(self):
        data = await self.store.async_load() or {}
        self.bills = data.get("bills", {})

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
            }
            await self.save()
        return bill_id

    def get(self, bill_id):
        if bill_id not in self.bills:
            raise HomeAssistantError(f"Unknown bill_id: {bill_id}")
        return self.bills[bill_id]

    async def update(self, data: dict):
        async with self.lock:
            bill = self.get(data["bill_id"])
            for field in ("name", "category"):
                if field in data:
                    bill[field] = data[field].strip()
            if "cost" in data:
                bill["cost"] = round(data["cost"], 2)
            if "due_date" in data:
                due = checked_date(data["due_date"])
                bill["due_date"] = due.isoformat()
                bill["due_day"] = due.day
            await self.save()

    async def set_paid(self, bill_id: str, paid: bool):
        async with self.lock:
            bill = self.get(bill_id)
            bill["paid"] = paid
            bill["paid_on"] = dt_util.now().date().isoformat() if paid else None
            await self.save()

    async def rollover(self, bill_id: str):
        async with self.lock:
            bill = self.get(bill_id)
            if not bill["paid"]:
                raise HomeAssistantError("Mark this bill Paid before rolling it over; unpaid occurrences are retained.")
            self.bills[bill_id] = roll_bill(bill)
            await self.save()

    async def delete(self, bill_id: str):
        async with self.lock:
            self.get(bill_id)
            del self.bills[bill_id]
            await self.save()

    async def daily_tick(self):
        """Advance paid bills after their due dates; preserve unpaid overdue bills."""
        async with self.lock:
            today = dt_util.now().date()
            changed = False
            for key, bill in list(self.bills.items()):
                if bill["paid"] and checked_date(bill["due_date"]) < today:
                    self.bills[key] = roll_bill(bill)
                    changed = True
            if changed:
                await self.save()
            else:
                self.notify()  # Upcoming -> Past Due at midnight


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Register actions once, including when no config entry exists yet."""
    hass.data.setdefault(DOMAIN, {})

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

    async def mark_unpaid(call: ServiceCall):
        await manager().set_paid(call.data["bill_id"], False)

    async def rollover(call: ServiceCall):
        await manager().rollover(call.data["bill_id"])

    async def delete_bill(call: ServiceCall):
        await manager().delete(call.data["bill_id"])

    hass.services.async_register(DOMAIN, "add_bill", add_bill, schema=ADD_SCHEMA)
    hass.services.async_register(DOMAIN, "update_bill", update_bill, schema=UPDATE_SCHEMA)
    hass.services.async_register(DOMAIN, "mark_paid", mark_paid, schema=TARGET_SCHEMA)
    hass.services.async_register(DOMAIN, "mark_unpaid", mark_unpaid, schema=TARGET_SCHEMA)
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
