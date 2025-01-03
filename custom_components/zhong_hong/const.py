from homeassistant.const import Platform

from typing import Final

import logging
_LOGGER = logging.getLogger(__name__)

DOMAIN: Final = "zhong_hong"
CONF_IP_ADDRESS: Final = "ip_address"
CONF_PORT: Final = 'port'
CONF_USERNAME: Final = 'username'
CONF_PASSWORD: Final = 'password'
CONF_REFRESH_INTERVAL: Final = "refresh_interval"

DEFAULT_USERNAME: Final = 'admin'
DEFAULT_PASSWORD: Final = ''
DEFAULT_PORT: Final = 9999
DEFAULT_REFRESH_INTERVAL = 60

PLATFORMS: Final = [
    Platform.SENSOR,
    Platform.CLIMATE
]