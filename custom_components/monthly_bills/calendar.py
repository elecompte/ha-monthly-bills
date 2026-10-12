"""A read-only calendar of all Monthly Bills due dates."""
from datetime import datetime

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.util import dt as dt_util

from .calendar_model import bill_events, current_or_next, events_between
from .const import DOMAIN, SIGNAL_CHANGED


async def async_setup_entry(hass, entry, async_add_entities):
    manager = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([MonthlyBillsCalendar(manager)])


class MonthlyBillsCalendar(CalendarEntity):
    """Expose the same stored due dates used by the bill controls."""
    _attr_name = "Monthly Bills"
    _attr_unique_id = "monthly_bills_due_dates"
    _attr_icon = "mdi:calendar-cash"
    _attr_should_poll = False
    _attr_supported_features = 0

    def __init__(self, manager):
        self.manager = manager

    def _events(self):
        return bill_events(self.manager.bills, dt_util.now().date())

    @property
    def event(self) -> CalendarEvent | None:
        event = current_or_next(self._events(), dt_util.now().date())
        return CalendarEvent(**event) if event else None

    async def async_get_events(self, hass, start_date: datetime, end_date: datetime):
        events = events_between(
            self._events(), dt_util.as_local(start_date), dt_util.as_local(end_date)
        )
        return [CalendarEvent(**event) for event in events]

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        self.async_on_remove(
            async_dispatcher_connect(self.hass, SIGNAL_CHANGED, self._bills_changed)
        )

    @callback
    def _bills_changed(self):
        self.async_write_ha_state()
        # Other bills can change while the calendar's next-event state is
        # unchanged. Explicitly notify calendar-card subscribers in that case.
        if notify := getattr(self, "async_update_event_listeners", None):
            notify()
