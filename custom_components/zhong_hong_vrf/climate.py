"""Climate entity for Zhong Hong VRF."""
from typing import Any

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    AC_MODE_OFF,
    AC_MODE_COOL,
    AC_MODE_DRY,
    AC_MODE_FAN,
    AC_MODE_HEAT,
    FAN_SPEED_AUTO,
    FAN_SPEED_LOW,
    FAN_SPEED_MEDIUM,
    FAN_SPEED_HIGH,
    API_TO_HA_MODE_MAPPING,
    API_TO_HA_FAN_MAPPING,
    HA_TO_API_MODE_MAPPING,
    HA_TO_API_FAN_MAPPING,
)
from .coordinator import ZhongHongDataUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: dict[str, Any],
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Zhong Hong VRF climate entities."""
    coordinator: ZhongHongDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities = []
    for device_key, device_data in coordinator.data["devices"].items():
        entities.append(ZhongHongClimate(coordinator, device_key, device_data))

    async_add_entities(entities)


class ZhongHongClimate(CoordinatorEntity, ClimateEntity):
    """Zhong Hong VRF climate entity."""

    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_has_entity_name = True
    _enable_turn_on_off_backwards_compatibility = False

    def __init__(
        self,
        coordinator: ZhongHongDataUpdateCoordinator,
        device_key: str,
        device_data: dict[str, Any],
    ) -> None:
        """Initialize the climate entity."""
        super().__init__(coordinator)
        self.device_key = device_key
        self.device_data = device_data

        oa, ia = device_key.split("_")
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{device_key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_key)},
            name=f"AC {oa}-{ia}",
            manufacturer=coordinator.data["device_info"]["manufacturer"],
            model=coordinator.data["device_info"]["model"],
            sw_version=coordinator.data["device_info"]["sw_version"],
            configuration_url=f"http://{coordinator.client.host}",
        )

        self._attr_hvac_modes = [
            HVACMode.OFF,
            HVACMode.COOL,
            HVACMode.DRY,
            HVACMode.FAN_ONLY,
            HVACMode.HEAT,
        ]
        self._attr_fan_modes = ["auto", "low", "medium", "high"]
        self._attr_supported_features = (
            ClimateEntityFeature.TARGET_TEMPERATURE
            | ClimateEntityFeature.FAN_MODE
            | ClimateEntityFeature.TURN_ON
            | ClimateEntityFeature.TURN_OFF
        )

        self._update_device_data(device_data)

    def _update_device_data(self, device_data: dict[str, Any]) -> None:
        """Update device data."""
        self.device_data = device_data

        # Current temperature
        try:
            self._attr_current_temperature = float(device_data.get("tempIn", 0))
        except (ValueError, TypeError):
            self._attr_current_temperature = None

        # Target temperature
        try:
            self._attr_target_temperature = float(device_data.get("tempSet", 25))
        except (ValueError, TypeError):
            self._attr_target_temperature = 25

        # HVAC mode
        on_state = device_data.get("on", 0)
        if on_state == 0:
            self._attr_hvac_mode = HVACMode.OFF
        else:
            ac_mode = int(device_data.get("mode", AC_MODE_COOL))
            self._attr_hvac_mode = API_TO_HA_MODE_MAPPING.get(ac_mode, HVACMode.COOL)

        # Fan mode
        fan_speed = int(device_data.get("fan", 0))
        self._attr_fan_mode = API_TO_HA_FAN_MAPPING.get(fan_speed, "auto")

        # HVAC action
        if on_state == 0:
            self._attr_hvac_action = "off"
        else:
            self._attr_hvac_action = "idle"

    @property
    def min_temp(self) -> float:
        """Return the minimum temperature."""
        try:
            return float(self.device_data.get("lowestVal", 16))
        except (ValueError, TypeError):
            return 16

    @property
    def max_temp(self) -> float:
        """Return the maximum temperature."""
        try:
            return float(self.device_data.get("highestVal", 30))
        except (ValueError, TypeError):
            return 30

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return

        await self._set_device_state(temp_set=int(temperature))

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target hvac mode."""
        if hvac_mode == HVACMode.OFF:
            await self._set_device_state(state=0)
        else:
            api_mode = HA_TO_API_MODE_MAPPING.get(hvac_mode, AC_MODE_COOL)
            await self._set_device_state(state=1, mode=api_mode)

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set new target fan mode."""
        fan_mapping = {
            "auto": FAN_SPEED_AUTO,
            "low": FAN_SPEED_LOW,
            "medium": FAN_SPEED_MEDIUM,
            "high": FAN_SPEED_HIGH,
        }

        fan_speed = fan_mapping.get(fan_mode, FAN_SPEED_AUTO)
        await self._set_device_state(fan=fan_speed)

    async def async_turn_on(self) -> None:
        """Turn the entity on."""
        await self._set_device_state(state=1)

    async def async_turn_off(self) -> None:
        """Turn the entity off."""
        await self._set_device_state(state=0)

    async def _set_device_state(self, **kwargs: Any) -> None:
        """Set device state."""
        current_state = {
            "state": self.device_data.get("on", 0),
            "mode": self.device_data.get("mode", AC_MODE_COOL),
            "temp_set": self.device_data.get("tempSet", 25),
            "fan": self.device_data.get("fan", FAN_SPEED_AUTO),
        }
        current_state.update(kwargs)

        success = await self.coordinator.client.async_control_device(
            idx=self.device_data.get("idx", 0),
            state=current_state["state"],
            mode=current_state["mode"],
            temp_set=current_state["temp_set"],
            fan=current_state["fan"],
        )

        if success:
            self.device_data.update(current_state)
            self._update_device_data(self.device_data)
            self.async_write_ha_state()

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        device_data = self.coordinator.data["devices"].get(self.device_key)
        if device_data:
            self._update_device_data(device_data)
            self.async_write_ha_state()