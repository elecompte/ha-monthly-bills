"""Editable bill category."""
from homeassistant.components.text import TextEntity
from .bill_entity import BillEntity, setup_bill_entities

async def async_setup_entry(hass, entry, async_add_entities):
    setup_bill_entities(hass, entry, async_add_entities, BillCategory)

class BillCategory(BillEntity, TextEntity):
    _attr_name = "Category"
    _attr_icon = "mdi:shape"
    _attr_native_min = 1
    _attr_native_max = 100
    def __init__(self, manager, bill_id):
        super().__init__(manager, bill_id, "category")
    @property
    def native_value(self):
        return self.bill["category"] if self.available else None
    async def async_set_value(self, value):
        await self.manager.update({"bill_id": self.bill_id, "category": value})
