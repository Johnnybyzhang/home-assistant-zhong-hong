"""Config flow for Zhong Hong VRF integration."""

import asyncio
import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import (
    CONF_HOST,
    CONF_PORT,
    CONF_USERNAME,
    CONF_PASSWORD,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError

from .client import ZhongHongClient
from .const import (
    DEFAULT_PORT,
    DEFAULT_USERNAME,
    DEFAULT_PASSWORD,
    DOMAIN,
    DEFAULT_MIN_TEMP,
    DEFAULT_MAX_TEMP,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): int,
        vol.Optional(CONF_USERNAME, default=DEFAULT_USERNAME): str,
        vol.Optional(CONF_PASSWORD, default=DEFAULT_PASSWORD): str,
    }
)


async def validate_input(
    hass: HomeAssistant, data: dict[str, Any]
) -> dict[str, Any]:
    """Validate the user input allows us to connect."""
    client = ZhongHongClient(
        host=data[CONF_HOST],
        port=data[CONF_PORT],
        username=data[CONF_USERNAME],
        password=data[CONF_PASSWORD],
    )

    try:
        _LOGGER.info(
            "Validating connection to Zhong Hong VRF at %s:%s",
            data[CONF_HOST],
            data[CONF_PORT],
        )
        await client.async_setup()

        # Test connection by fetching device info
        _LOGGER.debug("Fetching device info...")
        device_info = await client.async_get_device_info()
        if not device_info:
            _LOGGER.error(
                "Failed to get device information from %s", data[CONF_HOST]
            )
            raise CannotConnect("Failed to get device information")

        _LOGGER.debug("Device info: %s", device_info)

        _LOGGER.debug("Fetching devices...")
        devices = await client.async_get_devices()
        _LOGGER.debug("Found %d devices", len(devices))
        if not devices:
            _LOGGER.warning("No devices found at %s", data[CONF_HOST])
            raise CannotConnect("No devices found")

        await client.async_shutdown()

        return {
            "title": f"Zhong Hong VRF ({data[CONF_HOST]})",
            "devices_count": len(devices),
            "manufacturer": device_info.get("manufacturer", "Zhong Hong"),
        }

    except OSError as ex:
        _LOGGER.error("Connection failed to %s: %s", data[CONF_HOST], ex)
        raise CannotConnect("Connection failed")
    except asyncio.TimeoutError:
        _LOGGER.error("Timeout connecting to %s", data[CONF_HOST])
        raise CannotConnect("Timeout connecting to device")
    except Exception as ex:
        _LOGGER.error("Validation error: %s", ex, exc_info=True)
        raise CannotConnect(str(ex))


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Zhong Hong VRF."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            try:
                _LOGGER.info(
                    "Processing Zhong Hong VRF configuration: %s", user_input
                )
                info = await validate_input(self.hass, user_input)
                _LOGGER.info("Configuration successful, creating entry")
                await self.async_set_unique_id(user_input[CONF_HOST])
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=info["title"], data=user_input
                )
            except CannotConnect as ex:
                _LOGGER.error("Cannot connect: %s", ex)
                errors["base"] = "cannot_connect"
            except Exception as ex:  # pylint: disable=broad-except
                _LOGGER.exception(
                    "Unexpected exception during validation: %s", ex
                )
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class ZhongHongOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options for Zhong Hong VRF."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        errors = {}
        if user_input is not None:
            min_temp = user_input.get("min_temp", DEFAULT_MIN_TEMP)
            max_temp = user_input.get("max_temp", DEFAULT_MAX_TEMP)
            if min_temp >= max_temp:
                errors["base"] = "invalid_temp_range"
            else:
                return self.async_create_entry(title="", data=user_input)

        options_schema = vol.Schema(
            {
                vol.Optional(
                    "min_temp",
                    default=self.config_entry.options.get("min_temp", DEFAULT_MIN_TEMP),
                ): int,
                vol.Optional(
                    "max_temp",
                    default=self.config_entry.options.get("max_temp", DEFAULT_MAX_TEMP),
                ): int,
            }
        )

        return self.async_show_form(
            step_id="init", data_schema=options_schema, errors=errors
        )


async def async_get_options_flow(config_entry: config_entries.ConfigEntry):
    return ZhongHongOptionsFlowHandler(config_entry)
