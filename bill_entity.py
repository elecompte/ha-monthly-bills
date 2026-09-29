"""Shared bill device and dynamic entity registration."""
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers import entity_registry as er, device_registry as dr
from homeassistant.core import callback
from homeassistant.helpers.entity import Entity
from .const import DOMAIN, SIGNAL_CHANGED

class BillEntity(Entity):
    _attr_should_poll = False

    def __init__(self, manager, bill_id, suffix):
        self.manager = manager
        self.bill_id = bill_id
        self._attr_unique_id = f"monthly_bill_{bill_id}" if suffix == "status" else f"monthly_bill_{bill_id}_{suffix}"
        self._attr_has_entity_name = True

    @property
    def device_info(self):
        bill = self.manager.bills.get(self.bill_id)
        if not bill:
            return None
        return {"identifiers": {(DOMAIN, self.bill_id)}, "name": bill["name"],
                "manufacturer": "Monthly Bills", "model": "Recurring bill"}

    @property
    def available(self):
        return self.bill_id in self.manager.bills

    @property
    def bill(self):
        return self.manager.bills[self.bill_id]


def setup_bill_entities(hass, entry, async_add_entities, cls):
    manager = hass.data[DOMAIN][entry.entry_id]
    entities = {}

    @callback
    def sync():
        for bill_id in set(manager.bills) - set(entities):
            obj = cls(manager, bill_id)
            entities[bill_id] = obj
            async_add_entities([obj])
        for bill_id in set(entities) - set(manager.bills):
            obj = entities.pop(bill_id)
            async def remove_deleted(target):
                registry = er.async_get(hass)
                entity_id = registry.async_get_entity_id(target.platform.domain, DOMAIN, target.unique_id)
                await target.async_remove()
                if entity_id is not None:
                    registry.async_remove(entity_id)
            if obj.hass is not None:
                hass.async_create_task(remove_deleted(obj))
        for obj in entities.values():
            if obj.hass is not None:
                obj.async_write_ha_state()

        # Remove device entries for bills deleted from persistent storage.
        registry = dr.async_get(hass)
        for device in dr.async_entries_for_config_entry(registry, entry.entry_id):
            if not any(domain == DOMAIN and ident in manager.bills for domain, ident in device.identifiers):
                registry.async_remove_device(device.id)

    entry.async_on_unload(async_dispatcher_connect(hass, SIGNAL_CHANGED, sync))
    sync()
