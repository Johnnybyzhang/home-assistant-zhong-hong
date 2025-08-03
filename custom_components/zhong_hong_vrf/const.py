"""Constants for Zhong Hong VRF integration."""

from typing import Final

DOMAIN: Final = "zhong_hong_vrf"

DEFAULT_PORT: Final = 9999
DEFAULT_USERNAME: Final = "admin"
DEFAULT_PASSWORD: Final = ""

DEFAULT_MIN_TEMP: Final = 16
DEFAULT_MAX_TEMP: Final = 30

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

# AC Brand mappings
AC_BRANDS = {
    1: "Hitachi",
    2: "Daikin",
    3: "Toshiba",
    4: "Mitsubishi Heavy Industries",
    5: "Mitsubishi Electric",
    6: "Gree",
    7: "Hisense",
    8: "Midea",
    9: "Haier",
    10: "LG",
    13: "Samsung",
    14: "AUX",
    15: "Panasonic",
    16: "York",
    19: "Gree 4th Gen",
    21: "McQuay",
    24: "TCL",
    25: "Chigo",
    26: "TICA",
    35: "CH-York",
    36: "CoolWind",
    37: "York Qingdao",
    38: "Fujitsu",
    39: "Samsung (NotNASA_BMS)",
    40: "Samsung (NASA_BMS)",
    42: "Fudiwosi",
    43: "B23",
    44: "EK",
    45: "Hitachi Q3 Converter",
    46: "YCJ",
    47: "Depulaite",
    48: "Hailin A8033 Thermostat",
    49: "Midea CoolWind (Special Protocol)",
    50: "HITACHI Mini",
    56: "HL8023MD Thermostat",
    58: "Bole",
    59: "Tianlang (Five Constant System)",
    101: "CH-Emerson",
    102: "CH-McQuay",
    103: "Trane",
    104: "CH-Carrier",
    105: "CH-York (A1B1)",
    126: "Toshiba (Central Control Address)",
    128: "GREE_M",
    129: "McQuay_M",
    131: "Midea Modular",
    132: "DUNAN_M",
    134: "TICA Modular",
    135: "Guoxiang_M",
    253: "Mitsubishi Heavy Industries (KX4)",
    255: "Simulator",
    381: "Fujitsu Protocol Converter",
}
