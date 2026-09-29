"""Status sensor and history attributes for each bill."""
from homeassistant.components.sensor import SensorEntity
from homeassistant.util import dt as dt_util
from .bill_entity import BillEntity, setup_bill_entities
from .model import status_for

async def async_setup_entry(hass, entry, async_add_entities):
    setup_bill_entities(hass, entry, async_add_entities, BillStatus)

class BillStatus(BillEntity, SensorEntity):
    _attr_name = "Status"
    _attr_icon = "mdi:receipt-text"
    def __init__(self, manager, bill_id):
        super().__init__(manager, bill_id, "status")
    @property
    def native_value(self):
        return status_for(self.bill, dt_util.now().date()) if self.available else None
    @property
    def extra_state_attributes(self):
        if not self.available: return {}
        bill = self.bill
        return {"bill_id": self.bill_id, "cost": bill["cost"],
                "due_date": bill["due_date"], "payment_status": status_for(bill, dt_util.now().date()),
                "category": bill["category"], "paid": bill["paid"], "paid_on": bill["paid_on"],
                "recurring": "monthly", "payment_history": list(bill.get("history", []))}
