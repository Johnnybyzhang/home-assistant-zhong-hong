from datetime import timedelta
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.core import HomeAssistant

from .const import  (
    DOMAIN, 
    PLATFORMS, 
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

from .client import ZhongHongGateway

import logging
_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up the Zhonghong component from a config entry."""
    ip_address = entry.data[CONF_IP_ADDRESS]
    port = entry.options.get(CONF_PORT, DEFAULT_PORT)
    username = entry.options.get(CONF_USERNAME, DEFAULT_USERNAME)
    password = entry.options.get(CONF_PASSWORD, DEFAULT_PASSWORD)
    scan_interval = entry.options.get(CONF_REFRESH_INTERVAL, DEFAULT_REFRESH_INTERVAL)

    coordinator = ZhongHongDataCoordinator(hass, ip_address, port, username, password, scan_interval)
    await coordinator.client.async_get_device_info()
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    coordinator.client.start_listen()

    return True

class ZhongHongDataCoordinator(DataUpdateCoordinator):
    def __init__(self, hass, ip_address, port, username, password, scan_interval):
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=scan_interval),
        )
        self.ip_address = ip_address
        self.client = ZhongHongGateway(ip_address, port, username, password)
        self.client.register_update_callback(self._on_client_devices_updated)

    def _unregister_update_callback(self):
        self.client.unregister_update_callback(self._on_client_devices_updated)

    def _on_client_devices_updated(self):
        self.hass.loop.call_soon_threadsafe(
            self.async_set_updated_data, self.client.devices
        )

    async def _async_update_data(self):
        await self.client.async_ac_list()
        if self.client.devices == {}:
            raise UpdateFailed(f"Error fetching ac list")
        return self.client.devices

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    hass.data[DOMAIN][entry.entry_id]._unregister_update_callback()
    hass.data[DOMAIN].pop(entry.entry_id)
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
