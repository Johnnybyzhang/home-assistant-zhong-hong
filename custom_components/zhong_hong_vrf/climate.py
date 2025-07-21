"""Climate entity for Zhong Hong VRF."""
import logging
from typing import Any

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    AC_MODE_COOL,
    FAN_SPEED_AUTO,
    FAN_SPEED_LOW,
    FAN_SPEED_MEDIUM,
    FAN_SPEED_HIGH,
    API_TO_HA_MODE_MAPPING,
    API_TO_HA_FAN_MAPPING,
    HA_TO_API_MODE_MAPPING,
)
from .coordinator import ZhongHongDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


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
        self._last_manual_update = None
        self._manual_update_timeout = 5  # seconds to prefer manual updates over coordinator

        oa, ia = device_key.split("_")
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{device_key}"
        
        # Ensure we have a proper device name
        device_name = f"AC {oa}-{ia}"
        self._attr_name = device_name
        
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_key)},
            name=device_name,
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

    def _update_device_data(self, device_data: dict[str, Any], *, from_coordinator: bool = True) -> None:
        """Update device data.

        The ``from_coordinator`` flag indicates whether this update originates
        from the periodic coordinator refresh. When ``False`` (e.g. after a
        manual state change), the debouncing check is skipped so the new values
        are applied immediately.
        """
        import time

        # Skip coordinator updates shortly after a manual change to avoid
        # overwriting the freshly set values with stale data from the gateway.
        if from_coordinator and self._last_manual_update:
            time_since_manual = time.time() - self._last_manual_update
            if time_since_manual < self._manual_update_timeout:
                _LOGGER.debug(
                    "Skipping coordinator update for %s due to recent manual change (%.1fs ago)",
                    self.name,
                    time_since_manual,
                )
                return

        self.device_data = device_data
        
        _LOGGER.debug("Device data update for %s: %s", self.name, device_data)
        
        # Log temperature range for debugging
        try:
            lowest = float(device_data.get("lowestVal", 16))
            highest = float(device_data.get("highestVal", 30))
            _LOGGER.debug(
                "Temperature range for %s: lowest=%.1f, highest=%.1f, current_set=%s, current_in=%s",
                self.name, lowest, highest, device_data.get("tempSet"), device_data.get("tempIn")
            )
        except (ValueError, TypeError) as e:
            _LOGGER.debug("Error parsing temperature range for %s: %s", self.name, e)

        # Current temperature - handle both string and int values
        try:
            temp_in = device_data.get("tempIn", 0)
            if isinstance(temp_in, str):
                temp_in = float(temp_in)
            self._attr_current_temperature = float(temp_in)
        except (ValueError, TypeError):
            self._attr_current_temperature = None

        # Target temperature - handle both string and int values
        try:
            temp_set = device_data.get("tempSet", 25)
            if isinstance(temp_set, str):
                temp_set = float(temp_set)
            self._attr_target_temperature = float(temp_set)
            _LOGGER.debug(
                "Updated target temperature for %s: %.1f°C",
                self.name, self._attr_target_temperature
            )
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
            min_val = float(self.device_data.get("lowestVal", 16))
            # Ensure min is not equal to or greater than max
            max_val = float(self.device_data.get("highestVal", 30))
            if min_val >= max_val:
                _LOGGER.warning(
                    "Invalid temperature range from device: min=%.1f, max=%.1f, using defaults",
                    min_val, max_val
                )
                return 16.0
            return min_val
        except (ValueError, TypeError):
            return 16.0

    @property
    def max_temp(self) -> float:
        """Return the maximum temperature."""
        try:
            max_val = float(self.device_data.get("highestVal", 30))
            min_val = float(self.device_data.get("lowestVal", 16))
            if max_val <= min_val:
                _LOGGER.warning(
                    "Invalid temperature range from device: min=%.1f, max=%.1f, using defaults",
                    min_val, max_val
                )
                return 30.0
            return max_val
        except (ValueError, TypeError):
            return 30.0

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            _LOGGER.debug("No temperature provided in set_temperature call")
            return

        # Ensure temperature is within valid range and properly formatted
        min_temp = self.min_temp
        max_temp = self.max_temp
        
        _LOGGER.debug(
            "Setting temperature for %s: requested=%.1f, min=%.1f, max=%.1f",
            self.name, temperature, min_temp, max_temp
        )
        
        # Clamp temperature to valid range
        temperature = max(min_temp, min(max_temp, temperature))
        temp_int = int(round(temperature))
        
        _LOGGER.debug(
            "Final temperature value for API call: %s (rounded from %.1f)",
            temp_int, temperature
        )
        
        await self._set_device_state(temp_set=temp_int)

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

        import time
        # Mark when the manual change was initiated so any in-flight coordinator
        # refreshes are ignored while the command is processed.
        self._last_manual_update = time.time()

        success = await self.coordinator.client.async_control_device(
            idx=self.device_data.get("idx", 0),
            state=current_state["state"],
            mode=current_state["mode"],
            temp_set=current_state["temp_set"],
            fan=current_state["fan"],
        )

        if success:
            # Immediately update the local device data
            self.device_data.update(current_state)
            # Apply the new state without triggering the debounce check
            self._update_device_data(self.device_data, from_coordinator=False)
            # Immediately write the state to Home Assistant
            self.async_write_ha_state()

            # Mark the time of this manual change so subsequent coordinator
            # updates are ignored for a short period to prevent racing.
            self._last_manual_update = time.time()
            
            _LOGGER.debug(
                "Successfully updated %s state: state=%s, mode=%s, temp_set=%s, fan=%s",
                self.name, current_state["state"], current_state["mode"], 
                current_state["temp_set"], current_state["fan"]
            )
        else:
            _LOGGER.error(
                "Failed to update %s state: state=%s, mode=%s, temp_set=%s, fan=%s",
                self.name, current_state["state"], current_state["mode"], 
                current_state["temp_set"], current_state["fan"]
            )

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        device_data = self.coordinator.data["devices"].get(self.device_key)
        if device_data:
            self._update_device_data(device_data)
            self.async_write_ha_state()