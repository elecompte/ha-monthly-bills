"""Editable current due date."""
from datetime import date
from homeassistant.components.date import DateEntity
from .bill_entity import BillEntity, setup_bill_entities

async def async_setup_entry(hass, entry, async_add_entities):
    setup_bill_entities(hass, entry, async_add_entities, BillDueDate)
    setup_bill_entities(hass, entry, async_add_entities, BillLastPaymentDate)

class BillDueDate(BillEntity, DateEntity):
    _attr_name = "Due date"
    _attr_icon = "mdi:calendar"
    def __init__(self, manager, bill_id):
        super().__init__(manager, bill_id, "due_date")
    @property
    def native_value(self):
        return date.fromisoformat(self.bill["due_date"]) if self.available else None
    async def async_set_value(self, value: date):
        await self.manager.update({"bill_id": self.bill_id, "due_date": value.isoformat()})


class BillLastPaymentDate(BillEntity, DateEntity):
    """Correction control for the most recently recorded payment."""
    _attr_name = "Last payment date"
    _attr_icon = "mdi:calendar-edit"

    def __init__(self, manager, bill_id):
        super().__init__(manager, bill_id, "last_payment_date")

    @property
    def native_value(self):
        value = self.bill.get("last_paid_on") if self.available else None
        return date.fromisoformat(value) if value else None

    async def async_set_value(self, value: date):
        await self.manager.correct_payment_date(self.bill_id, value)
