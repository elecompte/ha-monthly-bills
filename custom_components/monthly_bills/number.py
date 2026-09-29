"""Editable bill amount."""
from homeassistant.components.number import NumberEntity, NumberMode
from .bill_entity import BillEntity, setup_bill_entities

async def async_setup_entry(hass, entry, async_add_entities):
    setup_bill_entities(hass, entry, async_add_entities, BillAmount)

class BillAmount(BillEntity, NumberEntity):
    _attr_name = "Amount"
    _attr_icon = "mdi:currency-usd"
    _attr_native_min_value = 0
    _attr_native_max_value = 100000000
    _attr_native_step = 0.01
    _attr_native_unit_of_measurement = "USD"
    _attr_mode = NumberMode.BOX
    def __init__(self, manager, bill_id):
        super().__init__(manager, bill_id, "amount")
    @property
    def native_value(self):
        return self.bill["cost"] if self.available else None
    async def async_set_native_value(self, value):
        await self.manager.update({"bill_id": self.bill_id, "cost": float(value)})
