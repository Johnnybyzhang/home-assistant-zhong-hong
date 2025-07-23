"""HTTP/0.9 and TCP client for Zhong Hong VRF."""
import asyncio
import json
import logging
import socket
import time
from typing import Any, Dict, List, Optional, Callable
import aiohttp
from threading import Thread

from .const import DEFAULT_PORT, DEFAULT_USERNAME, DEFAULT_PASSWORD

_LOGGER = logging.getLogger(__name__)


class ZhongHongClient:
    """Client for Zhong Hong VRF HTTP/0.9 API and TCP socket."""

    def __init__(
        self,
        host: str,
        port: int = DEFAULT_PORT,
        username: str = DEFAULT_USERNAME,
        password: str = DEFAULT_PASSWORD,
    ) -> None:
        """Initialize the client."""
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        
        self._session: Optional[aiohttp.ClientSession] = None
        self._tcp_socket: Optional[socket.socket] = None
        self._listening = False
        self._tcp_thread: Optional[Thread] = None
        self._update_callbacks: List[Callable[[Dict[str, Any]], None]] = []
        
        self.devices: Dict[str, Dict[str, Any]] = {}
        self.device_info: Dict[str, str] = {}

    async def async_setup(self) -> None:
        """Set up the client."""
        _LOGGER.info("Setting up Zhong Hong client for %s:%s", self.host, self.port)
        
        # Configure session for HTTP/0.9 compatibility
        connector = aiohttp.TCPConnector(
            limit=10,
            keepalive_timeout=30,
            enable_cleanup_closed=True,
        )
        
        self._session = aiohttp.ClientSession(
            auth=aiohttp.BasicAuth(self.username, self.password),
            connector=connector,
            timeout=aiohttp.ClientTimeout(total=30),
            headers={"User-Agent": "ZhongHongVRF/1.0"},
        )
        
        _LOGGER.debug("HTTP client session created successfully")
        await self.async_refresh_devices()

    async def async_shutdown(self) -> None:
        """Shutdown the client."""
        if self._session:
            await self._session.close()
        self.stop_tcp_listener()

    def register_update_callback(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        """Register a callback for device updates."""
        if callback not in self._update_callbacks:
            self._update_callbacks.append(callback)

    def unregister_update_callback(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        """Unregister a callback."""
        if callback in self._update_callbacks:
            self._update_callbacks.remove(callback)

    def _notify_update_callbacks(self, device_data: Dict[str, Any]) -> None:
        """Notify all callbacks of device updates."""
        for callback in self._update_callbacks:
            try:
                callback(device_data)
            except Exception as ex:
                _LOGGER.error("Error in update callback: %s", ex)

    async def _async_get(self, url: str) -> Optional[Dict[str, Any]]:
        """Make HTTP/0.9 GET request using raw socket for compatibility."""
        try:
            return await self._async_get_http09(url)
        except Exception as ex:
            _LOGGER.error("HTTP/0.9 request failed, falling back: %s", ex)
            return None

    async def _async_get_http09(self, url: str) -> Optional[Dict[str, Any]]:
        """Use raw socket for HTTP/0.9 requests."""
        import urllib.parse
        
        parsed = urllib.parse.urlparse(url)
        host = parsed.hostname or self.host
        port = 80  # HTTP API always uses port 80
        path = parsed.path + (f"?{parsed.query}" if parsed.query else "")
        
        _LOGGER.debug("Making HTTP/0.9 request via raw socket to: %s:%s%s", host, port, path)
        
        try:
            # Create socket connection
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(host, port), timeout=10
            )
            
            # Build HTTP/0.9 request (minimal format)
            import base64
            auth_header = ""
            if self.username or self.password:
                credentials = f"{self.username}:{self.password}"
                encoded = base64.b64encode(credentials.encode('utf-8')).decode('ascii')
                auth_header = f"Authorization: Basic {encoded}\r\n"
            
            request = f"GET {path} HTTP/1.0\r\n"
            request += f"Host: {host}\r\n"
            request += auth_header
            request += "\r\n"
            
            # Send request
            writer.write(request.encode('utf-8'))
            await writer.drain()
            
            # Read response
            response_data = b""
            while True:
                chunk = await asyncio.wait_for(reader.read(1024), timeout=10)
                if not chunk:
                    break
                response_data += chunk
            
            writer.close()
            await writer.wait_closed()
            
            # Parse response (skip HTTP headers)
            response_text = response_data.decode('utf-8', errors='ignore')
            
            # Find JSON start (look for first '{' after headers)
            json_start = response_text.find('{')
            if json_start == -1:
                _LOGGER.error("No JSON found in response")
                return None
            
            json_str = response_text[json_start:]
            
            # Clean up any trailing data
            json_end = json_str.rfind('}')
            if json_end != -1:
                json_str = json_str[:json_end+1]
            
            result = json.loads(json_str)
            _LOGGER.debug("Successfully parsed HTTP/0.9 response: %s", result)
            return result
            
        except asyncio.TimeoutError:
            _LOGGER.error("HTTP/0.9 request timeout")
            return None
        except Exception as ex:
            _LOGGER.error("HTTP/0.9 socket error: %s", ex)
            return None

    async def _async_get_aiohttp_fallback(self, url: str) -> Optional[Dict[str, Any]]:
        """Fallback aiohttp method with improved HTTP/0.9 error handling."""
        if not self._session:
            _LOGGER.error("No session available for HTTP request")
            return None

        _LOGGER.debug("Making HTTP/0.9 request to: %s", url)
        try:
            timeout = aiohttp.ClientTimeout(total=10)
            async with self._session.get(url, timeout=timeout) as response:
                _LOGGER.debug("HTTP response status: %s", response.status)
                text = await response.text()
                _LOGGER.debug("Raw response text: %s", repr(text))
                
                try:
                    result = json.loads(text)
                    _LOGGER.debug("Parsed JSON response: %s", result)
                    return result
                except json.JSONDecodeError as e:
                    _LOGGER.error("Failed to parse JSON from response: %s", e)
                    return None
                    
        except aiohttp.ClientResponseError as ex:
            # Handle HTTP/0.9 format errors specifically
            _LOGGER.debug("Handling HTTP/0.9 response error: %s", str(ex))
            if ex.status == 400 and "Expected HTTP/" in str(ex):
                try:
                    # Extract the JSON from the exception message
                    message = str(ex)
                    
                    # Look for the JSON object directly
                    json_start = message.find('{"err"')
                    if json_start == -1:
                        json_start = message.find('{"')
                    
                    if json_start != -1:
                        # Find the last closing brace
                        json_end = message.rfind('}')
                        if json_end > json_start:
                            json_str = message[json_start:json_end+1]
                            # Clean up any remaining quotes or escape sequences
                            json_str = json_str.replace("\\'", "'").replace('\\"', '"')
                            result = json.loads(json_str)
                            _LOGGER.debug("Successfully parsed JSON from HTTP/0.9 error: %s", result)
                            return result
                except Exception as json_ex:
                    _LOGGER.error("Failed to parse JSON from HTTP/0.9 error: %s", json_ex)
                    _LOGGER.debug("Failed JSON string: %s", message[json_start:json_end+1] if 'json_start' in locals() else 'N/A')
                    
            _LOGGER.error("HTTP response error: %s", ex)
            return None
        except aiohttp.ClientConnectorError as ex:
            _LOGGER.error("Connection failed to %s: %s", self.host, ex)
            return None
        except asyncio.TimeoutError:
            _LOGGER.error("HTTP request timeout to %s", self.host)
            return None
        except Exception as ex:
            _LOGGER.error("HTTP request failed: %s (%s)" , type(ex).__name__, ex)
            return None

    async def async_get_devices(self) -> List[Dict[str, Any]]:
        """Get all devices via HTTP API by scanning all pages."""
        devices = []
        page = 0

        while True:
            url = f"http://{self.host}:80/cgi-bin/api.html?f=17&p={page}"
            response = await self._async_get(url)
            
            if not response or "unit" not in response:
                _LOGGER.debug("No units in response for page %d, stopping scan", page)
                break
                
            units = response["unit"]
            if not units:
                _LOGGER.debug("Empty units array for page %d, stopping scan", page)
                break
                
            _LOGGER.debug("Found %d devices on page %d", len(units), page)
            devices.extend(units)
            
            # Include partial pages - any page with less than 5 units is last page
            if len(units) < 5:
                _LOGGER.debug("Partial page (%d units) indicates end on page %d", len(units), page)
                break
                
            page += 1
            
            # Safety limit to prevent infinite loops
            if page > 20:
                _LOGGER.warning("Reached maximum page limit (20), stopping scan")
                break

        _LOGGER.info("Total devices discovered: %d", len(devices))
        return devices

    async def async_get_device_info(self) -> Dict[str, str]:
        """Get device information."""
        try:
            # Get brand info
            brand_response = await self._async_get(f"http://{self.host}:80/cgi-bin/api.html?f=24")
            brand = self._get_brand_name(brand_response.get("brand", 0) if brand_response else 0, brand_response.get("proto", 0) if brand_response else 0)

            # Get device info
            device_response = await self._async_get(f"http://{self.host}:80/cgi-bin/api.html?f=1")
            
            return {
                "manufacturer": brand,
                "model": device_response.get("model", "Unknown") if device_response else "Unknown",
                "sw_version": device_response.get("sw", "").strip() if device_response else "",
                "model_id": device_response.get("id", "") if device_response else "",
            }
        except Exception as ex:
            _LOGGER.error("Error getting device info: %s", ex)
            return {
                "manufacturer": "Zhong Hong",
                "model": "Unknown",
                "sw_version": "",
                "model_id": "",
            }

    def _get_brand_name(self, brand: int, proto: int) -> str:
        """Get brand name from brand ID."""
        brand_mapping = {
            1: "日立",
            2: "大金",
            3: "东芝",
            4: "三菱重工",
            5: "三菱电机",
            6: "格力",
            7: "海信",
            8: "美的",
            9: "海尔",
            10: "LG",
            13: "三星",
            14: "奥克斯",
            15: "松下",
            16: "约克",
            19: "格力四代",
            21: "麦克维尔",
            24: "TCL",
            25: "志高",
            26: "天加",
            35: "约克T8600",
            36: "酷风",
            37: "约克青岛",
            38: "富士通",
            39: "三星(NotNASA_BMS)",
            101: "CH-Emerson",
            102: "CH-麦克维尔",
            103: "特灵",
            255: f"模拟器{proto}台",
        }
        return brand_mapping.get(brand, "Unknown")

    async def async_refresh_devices(self) -> None:
        """Refresh device data from HTTP API."""
        devices = await self.async_get_devices()
        
        self.devices = {}
        for device in devices:
            key = f"{device.get('oa', 1)}_{device.get('ia', 1)}"
            self.devices[key] = device

        if not self.device_info:
            self.device_info = await self.async_get_device_info()

    async def async_control_device(
        self,
        idx: int,
        state: int,
        mode: int,
        temp_set: int,
        fan: int,
    ) -> bool:
        """Control a device via HTTP API."""
        url = (
            f"http://{self.host}:80/cgi-bin/api.html?"
            f"f=18&idx={idx}&on={state}&mode={mode}&tempSet={temp_set}&fan={fan}"
        )
        
        _LOGGER.debug(
            "Sending control command: idx=%s, on=%s, mode=%s, tempSet=%s, fan=%s",
            idx, state, mode, temp_set, fan
        )
        
        response = await self._async_get(url)
        success = response is not None and response.get("err") == 0
        
        _LOGGER.debug(
            "Control command result: success=%s, response=%s",
            success, response
        )
        
        return success

    def start_tcp_listener(self) -> None:
        """Start TCP socket listener for live updates."""
        if self._listening:
            return

        self._listening = True
        self._tcp_thread = Thread(target=self._tcp_listener_thread, daemon=True)
        self._tcp_thread.start()

    def stop_tcp_listener(self) -> None:
        """Stop TCP socket listener."""
        self._listening = False
        if self._tcp_socket:
            self._tcp_socket.close()
            self._tcp_socket = None
        if self._tcp_thread:
            self._tcp_thread.join(timeout=5)

    def _tcp_listener_thread(self) -> None:
        """TCP socket listener thread."""
        import logging
        # Reduce logging frequency for expected timeouts
        timeout_logger = logging.getLogger(f"{__name__}.tcp_timeout")
        timeout_logger.setLevel(logging.DEBUG)
        
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

        _LOGGER.info("Starting TCP socket listener on %s:%s", self.host, self.port)
        
        # Track consecutive timeouts to reduce log spam
        consecutive_timeouts = 0
        
        while self._listening:
            try:
                if not self._tcp_socket:
                    _LOGGER.debug("Creating new TCP socket connection")
                    self._tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    # Increase timeout for expected idle periods
                    self._tcp_socket.settimeout(30)
                    try:
                        self._tcp_socket.connect((self.host, self.port))
                        _LOGGER.info("TCP socket connected to %s:%s", self.host, self.port)
                        consecutive_timeouts = 0  # Reset on successful connection
                    except Exception as connect_ex:
                        _LOGGER.error("Failed to connect TCP socket: %s", connect_ex)
                        time.sleep(5)
                        continue

                data = self._tcp_socket.recv(1024)
                _LOGGER.debug("TCP received %d bytes: %s", len(data), data.hex() if data else "None")
                
                if not data:
                    _LOGGER.debug("No data received, sleeping...")
                    time.sleep(1)
                    continue

                # Reset timeout counter on successful data
                consecutive_timeouts = 0

                # Parse 25-byte packets
                offset = 0
                while offset + 25 <= len(data):
                    packet = data[offset:offset+25]
                    
                    # Check for valid packet header
                    if packet[:8] == b'\x55\xaa\x00\x04\x02\x01\x00\x0f':
                        payload = packet[8:23]
                        
                        # Verify CRC
                        if modbus_crc16(packet[:23]) == packet[23:25]:
                            # Verify payload checksum
                            if sum(payload[:-1]) & 0xFF == payload[-1]:
                                device_data = {
                                'grp': payload[0],
                                'oa': payload[4],
                                'ia': payload[5],
                                'on': payload[6],
                                'tempSet': payload[7],
                                'mode': payload[8],
                                'fan': payload[9],
                                'tempIn': payload[10],
                                'alarm': payload[11],
                            }
                                
                                key = f"{device_data['oa']}_{device_data['ia']}"
                                _LOGGER.debug("TCP device key: %s from payload: %s", key, payload.hex())
                                _LOGGER.debug("Known devices: %s", list(self.devices.keys()))
                                if key in self.devices:
                                    self.devices[key].update(device_data)
                                    full_data = dict(self.devices[key])
                                    _LOGGER.debug("TCP update for device %s: %s", key, full_data)
                                    self._notify_update_callbacks(full_data)
                                else:
                                    _LOGGER.debug("TCP received data for unknown device %s", key)
                    
                    offset += 1  # Check every possible starting position

            except socket.timeout:
                consecutive_timeouts += 1
                # Log timeout only occasionally to reduce spam
                if consecutive_timeouts % 30 == 1:  # Log roughly every minute
                    _LOGGER.debug("TCP socket timeout (expected when idle)")
                continue  # No sleep added - maintain original behavior
            except socket.error as sock_ex:
                _LOGGER.error("TCP socket error: %s", sock_ex)
                if self._tcp_socket:
                    self._tcp_socket.close()
                    self._tcp_socket = None
                time.sleep(5)
            except Exception as ex:
                _LOGGER.error("TCP listener error: %s", ex)
                time.sleep(5)
