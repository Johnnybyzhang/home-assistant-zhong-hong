
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.entity import EntityCategory
from homeassistant.components.sensor import (
    SensorEntity,
)
from .const import DOMAIN
from .client import AC_Feature

import logging
_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up Zhonghong climate entity from a config entry."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]

    sensors = []
    for ac_name, config in coordinator.data.items():
        sensors.append(ZhongHongSensor(coordinator=coordinator, ac_name=ac_name, config=config))
    async_add_entities(
        sensors, 
        update_before_add=True
    )


class ZhongHongSensor(CoordinatorEntity, SensorEntity):
    def __init__(self, coordinator, ac_name, config):
        super().__init__(coordinator)
        self._ac_name = ac_name
        self._attr_name = f'{self._ac_name} Alarm'
        self._attr_entity_category = EntityCategory.DIAGNOSTIC
        self._device_info = self.coordinator.client.device_info.copy()
        self._device_info['identifiers'] = {(DOMAIN, config[AC_Feature.GROUP] + 1)}

    @property
    def unique_id(self):
        """Return the unique ID of the HVAC."""
        return f"zhong_hong_http_{self._ac_name}_alarm"

    @property
    def device_info(self):
        """Return information to link this entity with the correct device."""
        return self._device_info

    @property
    def has_entity_name(self) -> bool:
        """Indicate that entity has name defined."""
        return True

    @property
    def icon(self) -> str:
        """Set icon."""
        return 'mdi:alert-circle'

    @property
    def state(self):
        return self.coordinator.data.get(self._ac_name).get(AC_Feature.ALARM)
