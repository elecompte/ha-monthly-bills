"""Status sensor and history attributes for each bill."""
from datetime import date
from homeassistant.components.sensor import SensorEntity, SensorDeviceClass
from homeassistant.util import dt as dt_util
from .bill_entity import BillEntity, setup_bill_entities
from .model import paid_for_display, status_for

async def async_setup_entry(hass, entry, async_add_entities):
    setup_bill_entities(hass, entry, async_add_entities, BillStatus)
    setup_bill_entities(hass, entry, async_add_entities, BillLastPaid)

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
                "category": bill["category"], "paid": paid_for_display(bill, dt_util.now().date()), "paid_on": bill["paid_on"],
                "auto_advance_due_date": bill["auto_advance_due_date"],
                "autopay": bill["autopay"],
                "upcoming_threshold_days": bill["upcoming_threshold_days"],
                "last_paid_on": bill["last_paid_on"], "last_paid_due_date": bill["last_paid_due_date"],
                "recurring": "monthly", "payment_history": list(bill.get("history", []))}


class BillLastPaid(BillEntity, SensorEntity):
    _attr_name = "Last paid"
    _attr_icon = "mdi:calendar-check"
    _attr_device_class = SensorDeviceClass.DATE

    def __init__(self, manager, bill_id):
        super().__init__(manager, bill_id, "last_paid")

    @property
    def native_value(self):
        value = self.bill.get("last_paid_on") if self.available else None
        return date.fromisoformat(value) if value else None
