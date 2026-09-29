"""Mark the current bill occurrence paid or unpaid."""
from homeassistant.components.switch import SwitchEntity
from .bill_entity import BillEntity, setup_bill_entities

async def async_setup_entry(hass, entry, async_add_entities):
    setup_bill_entities(hass, entry, async_add_entities, BillPaid)

class BillPaid(BillEntity, SwitchEntity):
    _attr_name = "Paid"
    _attr_icon = "mdi:cash-check"
    def __init__(self, manager, bill_id):
        super().__init__(manager, bill_id, "paid")
    @property
    def is_on(self):
        return self.bill["paid"] if self.available else None
    async def async_turn_on(self, **kwargs):
        await self.manager.set_paid(self.bill_id, True)
    async def async_turn_off(self, **kwargs):
        await self.manager.set_paid(self.bill_id, False)
