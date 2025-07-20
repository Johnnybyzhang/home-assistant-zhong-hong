"""DataUpdateCoordinator for Zhong Hong VRF."""
import asyncio
import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_USERNAME, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .client import ZhongHongClient
from .const import DOMAIN, UPDATE_INTERVAL_HTTP

_LOGGER = logging.getLogger(__name__)


class ZhongHongDataUpdateCoordinator(DataUpdateCoordinator):
    """DataUpdateCoordinator for Zhong Hong VRF."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the coordinator."""
        self.client = ZhongHongClient(
            host=entry.data[CONF_HOST],
            port=entry.data.get(CONF_PORT, 9999),
            username=entry.data.get(CONF_USERNAME, "admin"),
            password=entry.data.get(CONF_PASSWORD, ""),
        )

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=UPDATE_INTERVAL_HTTP),
        )

    async def async_config_entry_first_refresh(self) -> None:
        """First refresh of the config entry."""
        await self.client.async_setup()
        await super().async_config_entry_first_refresh()
        self.client.start_tcp_listener()

    async def _async_update_data(self) -> dict:
        """Update data via HTTP API."""
        try:
            await self.client.async_refresh_devices()
            return {
                "devices": self.client.devices,
                "device_info": self.client.device_info,
            }
        except Exception as ex:
            raise UpdateFailed(f"Failed to update Zhong Hong VRF data: {ex}") from ex

    async def async_shutdown(self) -> None:
        """Shutdown the coordinator."""
        await self.client.async_shutdown()

    def register_device_callback(self, callback):
        """Register callback for device updates."""
        self.client.register_update_callback(callback)

    def unregister_device_callback(self, callback):
        """Unregister callback for device updates."""
        self.client.unregister_update_callback(callback)