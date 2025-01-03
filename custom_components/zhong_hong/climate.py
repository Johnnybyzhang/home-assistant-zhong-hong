from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.components.climate.const import (
    FAN_LOW,
    FAN_MEDIUM,
    FAN_HIGH
)
from homeassistant.const import (
    ATTR_TEMPERATURE,
    UnitOfTemperature,
)
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from .const import DOMAIN, CONF_IP_ADDRESS
from .client import AC_Feature

import logging
_LOGGER = logging.getLogger(__name__)

SUPPORTED_HVAC_MODES = {
    HVACMode.OFF: 0,
    HVACMode.COOL: 1,
    HVACMode.DRY: 2,
    HVACMode.FAN_ONLY: 4,
    HVACMode.HEAT: 8,
}

SUPPORTED_FAN_MODES = {
    # FAN_AUTO: 0,
    FAN_HIGH: 1,
    FAN_MEDIUM: 2,
    FAN_LOW: 4,
}

async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up Zhonghong climate entity from a config entry."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    gateway = config_entry.data[CONF_IP_ADDRESS]

    sensors = []
    for ac_name, config in coordinator.data.items():
        sensors.append(ZhongHongClimateEntity(coordinator=coordinator, gateway=gateway, ac_name=ac_name, config=config))
    async_add_entities(
        sensors, 
        update_before_add=True
    )

class ZhongHongClimateEntity(CoordinatorEntity, ClimateEntity):
    _attr_hvac_modes = [
        HVACMode.COOL,
        HVACMode.HEAT,
        HVACMode.DRY,
        HVACMode.FAN_ONLY,
        HVACMode.OFF,
    ]
    _attr_fan_modes = [
        FAN_HIGH,
        FAN_MEDIUM,
        FAN_LOW,
    ]
    _attr_should_poll = False
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.FAN_MODE
        | ClimateEntityFeature.TURN_OFF
        | ClimateEntityFeature.TURN_ON
    )
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _enable_turn_on_off_backwards_compatibility = False

    _attr_max_temp: float = 30
    _attr_min_temp: float = 16
    _attr_precision: float = 1

    def __init__(self, coordinator, gateway, ac_name, config):
        """初始化Zhonghong空调实体"""
        super().__init__(coordinator)
        # self._hass = hass
        self._gateway = gateway
        self._ac_name = ac_name
        self._idx = config[AC_Feature.AC_IDX]
        self._attr_name = self._ac_name

        self._current_operation = None
        self._current_temperature = None
        self._target_temperature = None
        self._current_fan_mode = None
        self.is_initialized = False
        self._device_info = self.coordinator.client.device_info.copy()
        self._device_info['identifiers'] = {(DOMAIN, config[AC_Feature.GROUP] + 1)}

    @property
    def unique_id(self):
        """Return the unique ID of the HVAC."""
        return f"zhong_hong_http_{self._ac_name}"

    @property
    def device_info(self):
        """Return information to link this entity with the correct device."""
        return self._device_info

    @property
    def has_entity_name(self) -> bool:
        """Indicate that entity has name defined."""
        return True

    @property
    def hvac_mode(self) -> HVACMode:
        """Return current operation ie. heat, cool, idle."""            
        if not self.is_on:
            return HVACMode.OFF
        mode_value = self.coordinator.data.get(self._ac_name).get(AC_Feature.MODE)
        for key, value in SUPPORTED_HVAC_MODES.items():
            if value == mode_value:
                return key
        return None

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return float(self.coordinator.data.get(self._ac_name).get(AC_Feature.TEMP_INDOOR))

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return float(self.coordinator.data.get(self._ac_name).get(AC_Feature.TEMP_SET))

    @property
    def target_temperature_step(self):
        """Return the supported step of target temperature."""
        return 1

    @property
    def is_on(self):
        """Return true if on."""
        state = self.coordinator.data.get(self._ac_name).get(AC_Feature.STATE) == 1
        _LOGGER.debug(f'{self._ac_name} state: {state}')
        return state

    @property
    def fan_mode(self):
        """Return the fan setting."""
        fan_value = self.coordinator.data.get(self._ac_name).get(AC_Feature.FAN)
        for key, value in SUPPORTED_FAN_MODES.items():
            if value == fan_value:
                return key
        return None

    async def async_set_temperature(self, **kwargs) -> None:
        """Set new target temperature."""
        if (temperature := kwargs.get(ATTR_TEMPERATURE)) is not None:
            _LOGGER.debug(f'async_set_temperature: {temperature}')
            await self._send_control_command({AC_Feature.STATE: 1, AC_Feature.TEMP_SET: temperature})

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """设置新的HVAC模式并发送控制命令"""
        _LOGGER.debug(f'async_set_hvac_mode: {hvac_mode}')
        if hvac_mode ==  HVACMode.OFF:
            if self.is_on:
                await self._send_control_command({AC_Feature.STATE: 0})
            return

        mode = SUPPORTED_HVAC_MODES.get(hvac_mode, 0)
        await self._send_control_command({AC_Feature.STATE: 1, AC_Feature.MODE: mode})

    async def async_set_fan_mode(self, fan_mode) -> None:
        """设置新的风速模式并发送控制命令"""
        _LOGGER.debug(f'async_set_fan_mode: {fan_mode}')
        fan_speed = SUPPORTED_FAN_MODES.get(fan_mode, 0)
        await self._send_control_command({AC_Feature.STATE: 1, AC_Feature.FAN: fan_speed})

    async def _send_control_command(self, ac_json):
        """向网关发送控制命令"""        
        await self.coordinator.client.async_set_ac(self._ac_name, self._idx, ac_json)
