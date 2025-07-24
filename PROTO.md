# Zhong Hong VRF Protocol Documentation

This document describes the communication protocols used by the Zhong Hong VRF system for integration with Home Assistant.

## Overview

The Zhong Hong VRF system uses a **hybrid communication approach**:
- **HTTP/0.9 API** for control commands and device discovery
- **TCP Socket** for real-time status updates
- **No control via TCP** - TCP is receive-only for live data

## HTTP/0.9 API Protocol

### Connection Details
- **Protocol**: HTTP/0.9 (requires special handling)
- **Port**: 80 (default)
- **Authentication**: Basic Auth (username/password)
- **Default Credentials**: admin/(empty)
- **Implementation**: Requests are sent using a raw TCP socket without any aiohttp fallback

### API Endpoints

#### 1. Device Information (`f=1`)
```
GET /cgi-bin/api.html?f=1
Response: {"err":0,"model":"000","sw":"44.71.00.00.006  ","id":"...","hwerror":"00","moduleerror":"00"}
```

#### 2. AC List (`f=17&p={page}`)
```
GET /cgi-bin/api.html?f=17&p=0
Response: {"err":0,"unit":[...]}
```

**Device Object Structure**:
```json
{
  "oa": 1,           // Outdoor unit number
  "ia": 1,           // Indoor unit number  
  "nm": "",          // Name (usually empty)
  "on": 1,           // Power state (0=off, 1=on)
  "mode": 1,         // Operation mode
  "alarm": 0,        // Alarm code
  "tempSet": "25",   // Target temperature
  "tempIn": "25",    // Current temperature
  "fan": 0,          // Fan speed
  "idx": 0,          // Device index for control
  "grp": 0,          // Group number
  "OnoffLock": 0,
  "tempLock": 0,
  "highestVal": 25,  // TempHigh for dual setpoint systems
  "lowestVal": 25,   // TempLow for dual setpoint systems
  "modeLock": 0,
  "FlowDirection1": 0,
  "FlowDirection2": 0,
  "MainRmc": 0
}
```

#### 3. Brand Information (`f=24`)
```
GET /cgi-bin/api.html?f=24
Response: {"err":0,"brand":3,"proto":0,"maxnum":32}
```

#### 4. Device Control (`f=18`)
```
GET /cgi-bin/api.html?f=18&idx={idx}&on={state}&mode={mode}&tempSet={temp}&fan={fan}
Response: {"err":0}
```

**Parameters**:
- `idx`: Device index (from AC list)
- `on`: Power state (0=off, 1=on)
- `mode`: Operation mode (see mapping below)
- `tempSet`: Target temperature (16-30°C, 1°C steps)
- `fan`: Fan speed (see mapping below)

### Mode Mapping
| Zhong Hong | Home Assistant |
|------------|----------------|
| 0 | off |
| 1 | auto |
| 2 | cool |
| 3 | dry |
| 4 | heat |
| 5 | fan_only |

### Fan Speed Mapping
| Zhong Hong | Home Assistant |
|------------|----------------|
| 0 | auto |
| 1 | low |
| 2 | medium |
| 3 | high |
| 4 | high (turbo) |

### Brand Mapping
| ID | Brand |
|----|--------|
| 1 | 日立 (Hitachi) |
| 2 | 大金 (Daikin) |
| 3 | 东芝 (Toshiba) |
| 4 | 三菱重工 (Mitsubishi Heavy) |
| 5 | 三菱电机 (Mitsubishi Electric) |
| 6 | 格力 (Gree) |
| 7 | 海信 (Hisense) |
| 8 | 美的 (Midea) |
| 9 | 海尔 (Haier) |
| 10 | LG |
| 13 | 三星 (Samsung) |
| 255 | Simulator |

## TCP Socket Protocol

### Connection Details
- **Protocol**: Binary with Modbus CRC
- **Port**: 9999 (configurable)
- **Format**: Receive-only, no control commands

### Packet Structure (25 bytes)
```
[Header: 8 bytes][Payload: 15 bytes][CRC: 2 bytes]
```

#### Header Format
```
55 AA 00 04 02 01 00 0F
```

#### Payload Format (15 bytes)
| Byte | Field | Description |
|------|-------|-------------|
| 0 | group | Group number |
| 1-3 | reserved | Not used |
| 4 | outdoor | Outdoor unit number |
| 5 | indoor | Indoor unit number |
| 6 | state | Power state (0/1) |
| 7 | tempSet | Target temperature |
| 8 | mode | Operation mode |
| 9 | fan | Fan speed |
| 10 | tempIn | Current temperature |
| 11 | alarm | Alarm code |
| 12-13 | reserved | Not used |
| 14 | checksum | Simple checksum |

#### CRC Calculation (Modbus CRC16)
```python
def modbus_crc16(data):
    crc = 0xFFFF
    for pos in data:
        crc ^= pos
        for _ in range(8):
            if (crc & 0x0001) != 0:
                crc >>= 1
                crc ^= 0xA001
            else:
                crc >>= 1
    return crc.to_bytes(2, byteorder='little')
```

#### Checksum Validation
```python
# Verify payload checksum
if sum(payload[:-1]) & 0xFF != payload[-1]:
    # Invalid packet
```

### Example TCP Packet
```
Hex: 55aa00040201000f01500101020501180100180000008c1975
Decoded: Group=1, Outdoor=2, Indoor=5, State=1, TempSet=24°C, TempIn=24°C, Fan=0, Alarm=0
```

## Device Identification

Devices are uniquely identified using the format: `{group}_{outdoor}_{indoor}`
- Example: `0_1_1` (Group 0, Outdoor 1, Indoor 1)
- This corresponds to the HTTP API's `grp`, `oa`, and `ia` fields

## Error Handling

### HTTP Error Codes
- `err: 0` - Success
- `err: 1` - General error
- Connection errors handled via asyncio timeout

### TCP Connection
- Automatic reconnection on socket errors
- 10-second timeout for TCP operations
- Background thread for continuous listening

## Integration Architecture

### Data Flow
1. **Discovery**: HTTP API fetches device list and info
2. **Control**: HTTP API sends commands to devices
3. **Live Updates**: TCP socket receives real-time status
4. **Polling**: HTTP API periodically refreshes full state

### Rate Limiting
- HTTP polling: 60-second intervals
- TCP retry: 10-second intervals on connection failure
- Control commands: Immediate execution

## Troubleshooting

### Common Issues
1. **HTTP/0.9 Connection**: Use `--http0.9` flag with curl
2. **Authentication**: Default credentials are admin/(empty)
3. **TCP Connection**: Ensure port 9999 is accessible
4. **Device Discovery**: Check if all devices appear in `f=17` response

### Debug Commands
```bash
# Test HTTP API
curl --http0.9 -u admin: "http://gateway-ip/cgi-bin/api.html?f=1"
curl --http0.9 -u admin: "http://gateway-ip/cgi-bin/api.html?f=17&p=0"

# Test TCP socket
nc gateway-ip 9999 | hexdump -C
```

## Protocol Limitations

1. **No TCP Control**: TCP socket is receive-only for status updates
2. **No Bulk Operations**: Each device must be controlled individually
3. **Limited Error Detail**: HTTP API provides minimal error information
4. **No Encryption**: All communications are unencrypted