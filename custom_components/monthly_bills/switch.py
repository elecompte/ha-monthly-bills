"""Mark the current bill occurrence paid or unpaid."""
from homeassistant.components.switch import SwitchEntity
from homeassistant.util import dt as dt_util
from homeassistant.helpers.entity import EntityCategory
from .model import paid_for_display
from .bill_entity import BillEntity, setup_bill_entities

async def async_setup_entry(hass, entry, async_add_entities):
    setup_bill_entities(hass, entry, async_add_entities, BillPaid)
    setup_bill_entities(hass, entry, async_add_entities, BillAutoAdvance)
    setup_bill_entities(hass, entry, async_add_entities, BillAutopay)

class BillPaid(BillEntity, SwitchEntity):
    _attr_name = "Paid"
    _attr_icon = "mdi:cash-check"
    def __init__(self, manager, bill_id):
        super().__init__(manager, bill_id, "paid")
    @property
    def is_on(self):
        return paid_for_display(self.bill, dt_util.now().date()) if self.available else None
    async def async_turn_on(self, **kwargs):
        await self.manager.set_paid(self.bill_id, True)
    async def async_turn_off(self, **kwargs):
        await self.manager.set_paid(self.bill_id, False)


class BillAutoAdvance(BillEntity, SwitchEntity):
    _attr_name = "Auto advance"
    _attr_icon = "mdi:calendar-arrow-right"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, manager, bill_id):
        super().__init__(manager, bill_id, "auto_advance")

    @property
    def is_on(self):
        return self.bill["auto_advance_due_date"] if self.available else None

    async def async_turn_on(self, **kwargs):
        await self.manager.update({"bill_id": self.bill_id, "auto_advance_due_date": True})

    async def async_turn_off(self, **kwargs):
        await self.manager.update({"bill_id": self.bill_id, "auto_advance_due_date": False})


class BillAutopay(BillEntity, SwitchEntity):
    """Track whether the bill is paid automatically by its provider."""
    _attr_name = "Autopay"
    _attr_icon = "mdi:credit-card-sync"

    def __init__(self, manager, bill_id):
        super().__init__(manager, bill_id, "autopay")

    @property
    def is_on(self):
        return self.bill["autopay"] if self.available else None

    async def async_turn_on(self, **kwargs):
        await self.manager.update({"bill_id": self.bill_id, "autopay": True})

    async def async_turn_off(self, **kwargs):
        await self.manager.update({"bill_id": self.bill_id, "autopay": False})
