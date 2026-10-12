"""Editable bill amount."""
from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.helpers.entity import EntityCategory
from .bill_entity import BillEntity, setup_bill_entities

async def async_setup_entry(hass, entry, async_add_entities):
    setup_bill_entities(hass, entry, async_add_entities, BillAmount)
    setup_bill_entities(hass, entry, async_add_entities, BillUpcomingThreshold)

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


class BillUpcomingThreshold(BillEntity, NumberEntity):
    _attr_name = "Upcoming threshold"
    _attr_icon = "mdi:calendar-clock"
    _attr_native_min_value = 0
    _attr_native_max_value = 30
    _attr_native_step = 1
    _attr_native_unit_of_measurement = "d"
    _attr_mode = NumberMode.BOX
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, manager, bill_id):
        super().__init__(manager, bill_id, "upcoming_threshold")

    @property
    def native_value(self):
        return self.bill["upcoming_threshold_days"] if self.available else None

    async def async_set_native_value(self, value):
        if not float(value).is_integer():
            raise ValueError("Upcoming threshold must be a whole number of days")
        await self.manager.update({"bill_id": self.bill_id, "upcoming_threshold_days": int(value)})
