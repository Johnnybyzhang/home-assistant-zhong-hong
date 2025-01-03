import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from .const import (
    DOMAIN, 
    CONF_IP_ADDRESS, 
    CONF_PORT, 
    CONF_USERNAME, 
    CONF_PASSWORD, 
    DEFAULT_PORT, 
    DEFAULT_USERNAME, 
    DEFAULT_PASSWORD, 
    CONF_REFRESH_INTERVAL, 
    DEFAULT_REFRESH_INTERVAL
)

import logging
_LOGGER = logging.getLogger(__name__)

class ZhonghongConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    async def async_step_user(self, user_input=None):
        if user_input is not None:            
            return self.async_create_entry(title=user_input[CONF_IP_ADDRESS], data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=self._get_schema(),
        )

    def _get_schema(self):
        """Return the schema for the user input."""
        return vol.Schema({
            vol.Required(CONF_IP_ADDRESS): str,
            vol.Optional(CONF_PORT, default=DEFAULT_PORT): int,
            vol.Optional(CONF_USERNAME, default=DEFAULT_USERNAME): str,
            vol.Optional(CONF_PASSWORD, default=DEFAULT_PASSWORD): str,
            vol.Optional(CONF_REFRESH_INTERVAL, default=DEFAULT_REFRESH_INTERVAL): int,
        })

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return ZhonghongOptionsFlow(config_entry)

class ZhonghongOptionsFlow(config_entries.OptionsFlow):
    def __init__(self, config_entry):
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_PORT, default=self.config_entry.options.get(CONF_PORT, DEFAULT_PORT)): int,
                    vol.Optional(CONF_USERNAME, default=self.config_entry.options.get(CONF_USERNAME, DEFAULT_USERNAME)): str,
                    vol.Optional(CONF_PASSWORD, default=self.config_entry.options.get(CONF_PASSWORD, DEFAULT_PASSWORD)): str,
                    vol.Optional(CONF_REFRESH_INTERVAL, default=self.config_entry.options.get(CONF_REFRESH_INTERVAL, DEFAULT_REFRESH_INTERVAL)): int
                }
            ),
        )

