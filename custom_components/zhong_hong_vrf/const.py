"""Constants for Zhong Hong VRF integration."""
from typing import Final

DOMAIN: Final = "zhong_hong_vrf"

DEFAULT_PORT: Final = 9999
DEFAULT_USERNAME: Final = "admin"
DEFAULT_PASSWORD: Final = ""

# Update intervals
UPDATE_INTERVAL_HTTP: Final = 60
UPDATE_INTERVAL_TCP_RETRY: Final = 10

# HVAC mode mappings from original component
AC_MODE_OFF = 0
AC_MODE_COOL = 1
AC_MODE_DRY = 2
AC_MODE_FAN = 4
AC_MODE_HEAT = 8

# Fan speeds from original component
FAN_SPEED_AUTO = 0
FAN_SPEED_HIGH = 1
FAN_SPEED_MEDIUM = 2
FAN_SPEED_LOW = 4

# Mapping to Home Assistant HVAC modes
API_TO_HA_MODE_MAPPING = {
    AC_MODE_OFF: "off",
    AC_MODE_COOL: "cool",
    AC_MODE_DRY: "dry",
    AC_MODE_FAN: "fan_only",
    AC_MODE_HEAT: "heat",
}

# Mapping from Home Assistant to API modes
HA_TO_API_MODE_MAPPING = {
    "off": AC_MODE_OFF,
    "cool": AC_MODE_COOL,
    "dry": AC_MODE_DRY,
    "fan_only": AC_MODE_FAN,
    "heat": AC_MODE_HEAT,
}

# Mapping to Home Assistant fan modes
API_TO_HA_FAN_MAPPING = {
    FAN_SPEED_AUTO: "auto",
    FAN_SPEED_LOW: "low",
    FAN_SPEED_MEDIUM: "medium",
    FAN_SPEED_HIGH: "high",
}

# Mapping from Home Assistant to API fan modes
HA_TO_API_FAN_MAPPING = {
    "auto": FAN_SPEED_AUTO,
    "low": FAN_SPEED_LOW,
    "medium": FAN_SPEED_MEDIUM,
    "high": FAN_SPEED_HIGH,
}