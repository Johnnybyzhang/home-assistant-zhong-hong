# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

Home Assistant custom integration for Zhong Hong VRF HVAC systems (specifically the green Mi version). Uses HTTP+TCP hybrid communication to reduce latency compared to pure HTTP.

## Architecture

- **Integration Type**: Home Assistant custom component (`custom_components/zhong_hong/`)
- **Communication**: Hybrid HTTP API + TCP socket for real-time updates
- **Platforms**: Climate (thermostat) + Sensor (diagnostic alarm)
- **Update Mechanism**: Coordinator pattern with background TCP listener thread

## Key Components

- `__init__.py`: Coordinator setup and device management
- `client.py`: Core communication library - HTTP API calls + TCP socket listener
- `climate.py`: Climate entity implementation for HVAC control
- `sensor.py`: Diagnostic sensor for alarm state
- `config_flow.py`: Configuration UI for setup
- `const.py`: Constants and configuration parameters

## Development Commands

### Testing Integration
```bash
# Install in Home Assistant custom_components
# Copy custom_components/zhong_hong/ to HA config/custom_components/
# Restart Home Assistant

# Validate configuration
hass --config-check

# Run Home Assistant with debug logging
hass -v --debug
```

### Manual Testing
```bash
# Test HTTP API calls manually
curl "http://<gateway-ip>/cgi-bin/api.html?f=1"  # Device info
curl "http://<gateway-ip>/cgi-bin/api.html?f=17&p=0"  # AC list
```

### Debug Logging
Enable debug logging in Home Assistant:
```yaml
logger:
  logs:
    custom_components.zhong_hong: debug
```

## Configuration

**Setup Parameters:**
- **IP Address**: Gateway IP (required)
- **Port**: TCP port (default: 9999)
- **Username**: HTTP auth (default: admin)
- **Password**: HTTP auth (default: empty)
- **Refresh Interval**: HTTP polling interval (default: 60s)

## Communication Protocol

1. **HTTP API**: Initial device discovery and control commands
   - Device info: `/cgi-bin/api.html?f=1`
   - AC list: `/cgi-bin/api.html?f=17&p={page}`
   - Control: `/cgi-bin/api.html?f=18&idx={idx}&on={state}&mode={mode}&tempSet={temp}&fan={fan}`

2. **TCP Socket**: Real-time status updates
   - Port 9999 (configurable)
   - Binary protocol with Modbus CRC
   - Background listener thread for continuous updates

## File Structure

```
custom_components/zhong_hong/
├── __init__.py          # Coordinator and setup
├── client.py            # Core communication library
├── climate.py           # Climate entity
├── sensor.py            # Diagnostic sensor
├── config_flow.py       # Configuration UI
├── const.py             # Constants
├── manifest.json        # Integration metadata
└── translations/        # UI translations
    ├── en.json
    └── zh-Hans.json
```

## Brand Support

Supports major HVAC brands via brand ID mapping (Hitachi, Daikin, Toshiba, Mitsubishi, Gree, Midea, etc.) - see `client.py:get_brand()` function.