"""HTTP/0.9 and TCP client for Zhong Hong VRF."""

import asyncio
import json
import logging
import socket
import time
from typing import Any, Dict, List, Optional, Callable
from threading import Thread, Lock

from .const import DEFAULT_PORT, DEFAULT_USERNAME, DEFAULT_PASSWORD, AC_BRANDS

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

        self._tcp_socket: Optional[socket.socket] = None
        self._listening = False
        self._tcp_thread: Optional[Thread] = None
        self._update_callbacks: List[Callable[[Dict[str, Any]], None]] = []

        # Asyncio integration
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._update_queue: Optional[asyncio.Queue] = None
        self._queue_task: Optional[asyncio.Task] = None

        # Synchronization primitives
        self._devices_lock = Lock()

        # Version tracking for device state
        self._version_counter = 0

        # Track connection status for availability
        self._tcp_connected = True

        self.devices: Dict[str, Dict[str, Any]] = {}
        self.device_info: Dict[str, str] = {}

    def _next_version(self) -> int:
        """Return the next monotonic version number."""
        self._version_counter += 1
        return self._version_counter

    async def _process_update_queue(self) -> None:
        """Process queued TCP updates in the event loop."""
        if not self._update_queue:
            return
        while self._listening:
            try:
                device_data = await self._update_queue.get()
                if device_data is None:
                    break
                self._notify_update_callbacks(device_data)
            except asyncio.CancelledError:
                break
            except Exception as ex:  # pragma: no cover - just log
                _LOGGER.error("Queue processing error: %s", ex)

    async def async_setup(self) -> None:
        """Set up the client."""
        _LOGGER.info(
            "Setting up Zhong Hong client for %s:%s", self.host, self.port
        )

        self._loop = asyncio.get_running_loop()
        self._update_queue = asyncio.Queue()

        _LOGGER.debug("Client setup complete")
        await self.async_refresh_devices()

    async def async_shutdown(self) -> None:
        """Shutdown the client."""
        self.stop_tcp_listener()
        if self._queue_task:
            self._queue_task.cancel()
            try:
                await self._queue_task
            except asyncio.CancelledError:
                pass

    def register_update_callback(
        self, callback: Callable[[Dict[str, Any]], None]
    ) -> None:
        """Register a callback for device updates."""
        if callback not in self._update_callbacks:
            self._update_callbacks.append(callback)

    def unregister_update_callback(
        self, callback: Callable[[Dict[str, Any]], None]
    ) -> None:
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

    @property
    def is_tcp_connected(self) -> bool:
        """Return TCP connection state."""
        return self._tcp_connected

    async def _async_get(self, url: str) -> Optional[Dict[str, Any]]:
        """Make HTTP/0.9 GET request using raw socket for compatibility."""
        try:
            return await self._async_get_http09(url)
        except asyncio.TimeoutError:
            _LOGGER.error("HTTP/0.9 request timeout")
            return None
        except OSError as ex:
            _LOGGER.error("HTTP/0.9 socket error: %s", ex)
            raise ConnectionError from ex
        except Exception as ex:
            _LOGGER.error("HTTP/0.9 request failed: %s", ex)
            raise ConnectionError from ex

    async def _async_get_http09(self, url: str) -> Optional[Dict[str, Any]]:
        """Use raw socket for HTTP/0.9 requests."""
        import urllib.parse

        parsed = urllib.parse.urlparse(url)
        host = parsed.hostname or self.host
        port = 80  # HTTP API always uses port 80
        path = parsed.path + (f"?{parsed.query}" if parsed.query else "")

        _LOGGER.debug(
            "Making HTTP/0.9 request via raw socket to: %s:%s%s",
            host,
            port,
            path,
        )

        writer = None
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
                encoded = base64.b64encode(credentials.encode("utf-8")).decode(
                    "ascii"
                )
                auth_header = f"Authorization: Basic {encoded}\r\n"

            request = f"GET {path} HTTP/1.0\r\n"
            request += f"Host: {host}\r\n"
            request += auth_header
            request += "\r\n"

            # Send request
            writer.write(request.encode("utf-8"))
            await writer.drain()

            # Read response
            response_data = b""
            while True:
                chunk = await asyncio.wait_for(reader.read(1024), timeout=10)
                if not chunk:
                    break
                response_data += chunk

            # Parse response (skip HTTP headers)
            response_text = response_data.decode("utf-8", errors="ignore")

            # Find JSON start (look for first '{' after headers)
            json_start = response_text.find("{")
            if json_start == -1:
                _LOGGER.error("No JSON found in response")
                return None

            json_str = response_text[json_start:]

            # Clean up any trailing data
            json_end = json_str.rfind("}")
            if json_end != -1:
                json_str = json_str[: json_end + 1]

            result = json.loads(json_str)
            _LOGGER.debug("Successfully parsed HTTP/0.9 response: %s", result)
            return result
        finally:
            if writer is not None:
                writer.close()
                try:
                    await writer.wait_closed()
                except Exception:  # pragma: no cover - best effort
                    pass


    async def async_get_devices(self) -> List[Dict[str, Any]]:
        """Get all devices via HTTP API by scanning all pages."""
        devices = []
        page = 0

        while True:
            url = f"http://{self.host}/cgi-bin/api.html?f=17&p={page}"
            response = await self._async_get(url)

            if not response or "unit" not in response:
                _LOGGER.debug("No units on page %d, stopping", page)
                break

            units = response["unit"]
            if not units:
                _LOGGER.debug("Empty units on page %d, stopping", page)
                break

            _LOGGER.debug("Found %d devices on page %d", len(units), page)
            devices.extend(units)

            # Include partial pages - <5 units is last
            if len(units) < 5:
                _LOGGER.debug(
                    "Partial page (%d units) indicates end on page %d",
                    len(units),
                    page,
                )
                break

            page += 1

            # Safety limit to prevent infinite loops
            if page > 20:
                _LOGGER.warning(
                    "Reached maximum page limit (20), stopping scan"
                )
                break

        _LOGGER.info("Total devices discovered: %d", len(devices))
        return devices

    async def async_get_device_info(self) -> Dict[str, str]:
        """Get device information."""
        try:
            # Get brand info
            brand_response = await self._async_get(
                f"http://{self.host}/cgi-bin/api.html?f=24"
            )
            brand = self._get_brand_name(
                brand_response.get("brand", 0) if brand_response else 0,
                brand_response.get("proto", 0) if brand_response else 0,
            )

            # Get device info
            device_response = await self._async_get(
                f"http://{self.host}/cgi-bin/api.html?f=1"
            )

            return {
                "manufacturer": brand,
                "model": (
                    device_response.get("model", "Unknown")
                    if device_response
                    else "Unknown"
                ),
                "sw_version": (
                    device_response.get("sw", "").strip()
                    if device_response
                    else ""
                ),
                "model_id": (
                    device_response.get("id", "") if device_response else ""
                ),
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
        if brand == 255:
            return f"Simulator {proto} units"
        return AC_BRANDS.get(brand, "Unknown")

    async def async_refresh_devices(self) -> None:
        """Refresh device data from HTTP API."""
        devices = await self.async_get_devices()

        self.devices = {}
        for device in devices:
            key = f"{device.get('oa', 1)}_{device.get('ia', 1)}"
            device["_version"] = self._next_version()
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
            f"http://{self.host}/cgi-bin/api.html?f=18&"
            f"idx={idx}&on={state}&mode={mode}&tempSet={temp_set}&fan={fan}"
        )

        _LOGGER.debug(
            "Control cmd: idx=%s, on=%s, mode=%s, tempSet=%s, fan=%s",
            idx,
            state,
            mode,
            temp_set,
            fan,
        )

        try:
            response = await self._async_get(url)
        except ConnectionError as ex:
            _LOGGER.error("Control request failed: %s", ex)
            return False

        success = response is not None and response.get("err") == 0

        _LOGGER.debug("Cmd result: success=%s, response=%s", success, response)

        return success

    def start_tcp_listener(self) -> None:
        """Start TCP socket listener for live updates."""
        if self._listening:
            return

        self._listening = True
        if self._loop and not self._queue_task:
            self._queue_task = self._loop.create_task(self._process_update_queue())
        self._tcp_thread = Thread(target=self._tcp_listener_thread, daemon=True)
        self._tcp_thread.start()

    def stop_tcp_listener(self) -> None:
        """Stop TCP socket listener."""
        self._listening = False
        self._tcp_connected = False
        if self._tcp_socket:
            self._tcp_socket.close()
            self._tcp_socket = None
        if self._tcp_thread:
            self._tcp_thread.join(timeout=5)
        if self._update_queue and self._loop:
            self._loop.call_soon_threadsafe(self._update_queue.put_nowait, None)

    def _tcp_listener_thread(self) -> None:
        """TCP socket listener thread."""

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
            return crc.to_bytes(2, byteorder="little")

        _LOGGER.info(
            "Starting TCP socket listener on %s:%s", self.host, self.port
        )

        while self._listening:
            try:
                _LOGGER.debug("Creating new TCP socket connection")
                self._tcp_socket = socket.socket(
                    socket.AF_INET, socket.SOCK_STREAM
                )
                self._tcp_socket.settimeout(10)
                try:
                    self._tcp_socket.connect((self.host, self.port))
                    _LOGGER.info(
                        "TCP connected to %s:%s", self.host, self.port
                    )
                    self._tcp_connected = True
                except Exception as connect_ex:
                    _LOGGER.error("TCP connect failed: %s", connect_ex)
                    self._tcp_connected = False
                    time.sleep(5)
                    continue

                data = self._tcp_socket.recv(1024)
                _LOGGER.debug(
                    "TCP received %d bytes: %s",
                    len(data),
                    data.hex() if data else "None",
                )

                if not data:
                    _LOGGER.debug("No data received, sleeping...")
                    time.sleep(1)
                    continue

                # Parse 25-byte packets
                offset = 0
                while offset + 25 <= len(data):
                    packet = data[offset : offset + 25]

                    # Check for valid packet header
                    if packet[:8] == b"\x55\xaa\x00\x04\x02\x01\x00\x0f":
                        payload = packet[8:23]

                        # Verify CRC
                        if modbus_crc16(packet[:23]) == packet[23:25]:
                            # Verify payload checksum
                            if sum(payload[:-1]) & 0xFF == payload[-1]:
                                device_data = {
                                    "grp": payload[0],
                                    "oa": payload[4],
                                    "ia": payload[5],
                                    "on": payload[6],
                                    "tempSet": payload[7],
                                    "mode": payload[8],
                                    "fan": payload[9],
                                    "tempIn": payload[10],
                                    "alarm": payload[11],
                                }
                                oa = device_data["oa"]
                                ia = device_data["ia"]
                                key = f"{oa}_{ia}"
                                _LOGGER.debug(
                                    "Devices: %s", list(self.devices.keys())
                                )
                                _LOGGER.debug(
                                    "Update %s: %s", key, device_data
                                )
                                if key in self.devices:
                                    with self._devices_lock:
                                        self.devices[key].update(device_data)
                                        self.devices[key]["_version"] = self._next_version()
                                    _LOGGER.debug(
                                        "TCP update for %s: %s",
                                        key,
                                        device_data,
                                    )
                                    if self._loop and self._update_queue:
                                        send_data = {"key": key, **device_data, "_version": self.devices[key]["_version"]}
                                        self._loop.call_soon_threadsafe(
                                            self._update_queue.put_nowait,
                                            send_data,
                                        )
                                else:
                                    _LOGGER.debug("Unknown device %s", key)

                    offset += 1  # Check every possible starting position

            except socket.timeout:
                _LOGGER.debug("TCP socket timeout, retrying...")
                continue
            except socket.error as sock_ex:
                _LOGGER.error("TCP socket error: %s", sock_ex)
                self._tcp_connected = False
                if self._tcp_socket:
                    self._tcp_socket.close()
                    self._tcp_socket = None
                time.sleep(5)
            except Exception as ex:
                _LOGGER.error("TCP listener error: %s", ex)
                self._tcp_connected = False
                time.sleep(5)
