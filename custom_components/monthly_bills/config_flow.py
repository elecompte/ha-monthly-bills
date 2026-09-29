"""Integration setup and bill management in the integration Options UI."""
import voluptuous as vol
from homeassistant import config_entries
from .const import DOMAIN
from homeassistant.helpers import selector

ADD_FORM = vol.Schema({
    vol.Required("name"): selector.TextSelector(),
    vol.Required("cost"): selector.NumberSelector(selector.NumberSelectorConfig(min=0, max=100000000, step=0.01, mode=selector.NumberSelectorMode.BOX)),
    vol.Required("due_date"): selector.DateSelector(),
    vol.Optional("category", default="Other"): selector.TextSelector(),
})

class MonthlyBillsConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()
        if user_input is not None:
            return self.async_create_entry(title="Monthly Bills", data={})
        return self.async_show_form(step_id="user", data_schema=vol.Schema({}))

    @staticmethod
    def async_get_options_flow(config_entry):
        return MonthlyBillsOptionsFlow()

class MonthlyBillsOptionsFlow(config_entries.OptionsFlow):
    async def async_step_init(self, user_input=None):
        return self.async_show_menu(step_id="init", menu_options=["add", "delete"])

    async def async_step_add(self, user_input=None):
        if user_input is not None:
            manager = self.hass.data[DOMAIN][self.config_entry.entry_id]
            try:
                await manager.add(user_input)
            except Exception:
                return self.async_show_form(step_id="add", data_schema=ADD_FORM, errors={"base": "invalid_bill"})
            return self.async_create_entry(title="", data={})
        return self.async_show_form(step_id="add", data_schema=ADD_FORM)

    async def async_step_delete(self, user_input=None):
        manager = self.hass.data[DOMAIN][self.config_entry.entry_id]
        if not manager.bills:
            return self.async_abort(reason="no_bills")
        if user_input is not None:
            await manager.delete(user_input["bill_id"])
            return self.async_create_entry(title="", data={})
        names = {bill_id: bill["name"] for bill_id, bill in manager.bills.items()}
        schema = vol.Schema({vol.Required("bill_id"): vol.In(names)})
        return self.async_show_form(step_id="delete", data_schema=schema)
