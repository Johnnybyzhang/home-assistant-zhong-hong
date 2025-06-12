"""Library to handle connection with ZhongHong HTTP Gateway."""

import socket
import time
from collections import defaultdict
from sys import platform
from threading import Thread
import aiohttp
import asyncio
import json

import logging
_LOGGER = logging.getLogger(__name__)
# _LOGGER.setLevel(logging.DEBUG)

SOCKET_BUFSIZE = 1024

from enum import StrEnum

class AC_Feature(StrEnum):
    GROUP = 'grp'
    AC_OUTDOOR = 'oa'
    AC_INDOOR = 'ia'
    AC_IDX = 'idx'
    STATE = 'on'
    TEMP_SET = 'tempSet'
    MODE = 'mode'
    FAN = 'fan'
    TEMP_INDOOR = 'tempIn'
    ALARM = 'alarm'

class Endpoint(StrEnum):
    HOST = "http://{gateway}/cgi-bin/api.html?"
    STATUS = 'f=17&p={p}'
    CONTROL = 'f=18&idx={idx}&on={on}&mode={mode}&tempSet={tempSet}&fan={fan}'
    AC_BRAND = f'f=24'
    DEVICE_INFO = f'f=1'

class ZhongHongGateway:
    def __init__(self, ip_addr: str, port: int, username: str = 'admin', password: str = ''):
        if platform not in ("darwin", "linux", "linux2"):
            raise Exception(f'platform {platform} is not supported.')
        
        self.ip_addr = ip_addr
        self.port = port
        self.sock = None
        self.devices = {}
        self._listening = False
        self._threads = []
        
        self.username = username
        self.password = password
        self._lock = asyncio.Lock()
        # self.update_callback = None
        self._update_callbacks = []
        self.device_info = {}

    # def register_update_callback(self, callback):
    #     """Register a callback to notify when devices are updated."""
    #     self.update_callback = callback

    def register_update_callback(self, callback):
        """Register a callback to notify when devices are updated."""
        if not callable(callback):
            raise ValueError("The callback must be a callable object.")
        if callback not in self._update_callbacks:
            self._update_callbacks.append(callback)

    def unregister_update_callback(self, callback):
        """Unregister a previously registered callback."""
        if callback in self._update_callbacks:
            self._update_callbacks.remove(callback)

    def _notify_update_callbacks(self):
        """Notify all registered callbacks."""
        for callback in self._update_callbacks:
            try:
                callback()
            except Exception as e:
                _LOGGER.error("Error in update callback: %s", e)

    async def parse_resp(self, url, data):
        try:
            _LOGGER.debug(f'async_get 400: data: {data}')
            parsed_data = data[data.find("'")+1:data.rfind("'")]
            return json.loads(parsed_data)
        except Exception as error:
            _LOGGER.debug(f'json parse failed: Error: {error}')
            return await self.async_get(url)

    async def async_get(self, url):
        """Make GET API call."""
        try:
            async with aiohttp.ClientSession(auth=aiohttp.BasicAuth(self.username, self.password), connector=aiohttp.TCPConnector()) as session:
                async with session.get(url) as resp:
                    _LOGGER.debug(f'async_get suceesfully: {url}. resp: {resp}')
                    return json.loads(await resp.text())
        except aiohttp.client_exceptions.ClientResponseError as error:
            if error.status == 400 and 'Expected HTTP/' in error.message:
                return await self.parse_resp(url, error.message)
            _LOGGER.debug(f'async_get failed 400: {url}. Error: {error}')
        except Exception as error:
            _LOGGER.debug(f'async_get failed: {url}. Error: {error}')
        return None

    async def async_ac_list(self, max_retries = 3):
        # async with self._lock:
        p = 0
        acs_list = []
        while max_retries > 0:
            url = f'{Endpoint.HOST.format(gateway=self.ip_addr)}{Endpoint.STATUS}'.format(p=p)
            resp = await self.async_get(url)
            if resp == None:
                max_retries = max_retries - 1
                await self.async_ac_list(max_retries)
                return
            unit = resp.get('unit', [])
            acs_list.extend(unit)
            if len(unit) == 0:
                break
            p += 1
        if max_retries > 0:
            self.devices = {
                f"{ac[AC_Feature.GROUP] + 1}_{ac[AC_Feature.AC_OUTDOOR]}_{ac[AC_Feature.AC_INDOOR]}": ac
                for ac in acs_list
            }
            if self._update_callbacks:
                self._notify_update_callbacks()

    async def async_set_ac(self, ac_name, idx, ac_json):
        async with self._lock:
            url = f'{Endpoint.HOST.format(gateway=self.ip_addr)}{Endpoint.CONTROL}'.format(
                idx = idx, 
                on=ac_json.get(AC_Feature.STATE,  self.devices.get(ac_name).get(AC_Feature.STATE)),
                mode=ac_json.get(AC_Feature.MODE, self.devices.get(ac_name).get(AC_Feature.MODE)),
                tempSet=ac_json.get(AC_Feature.TEMP_SET, self.devices.get(ac_name).get(AC_Feature.TEMP_SET)),
                fan=ac_json.get(AC_Feature.FAN, self.devices.get(ac_name).get(AC_Feature.FAN))
                )
            resp = await self.async_get(url)
            if resp == None:
                return
            
            self.devices[ac_name].update(ac_json)
            if self._update_callbacks:
                self._notify_update_callbacks()

    async def async_get_device_info(self):
        def get_brand(brand, proto):
            if brand == 1:
                return "日立"
            if brand == 2:
                return "大金"
            if brand == 3:
                return "东芝"
            if brand == 4:
                if proto > 0:
                    "三菱重工(KX4)"
                return "三菱重工"
            if brand == 5:
                return "三菱电机"
            if brand == 6:
                return "格力"
            if brand == 7:
                return "海信"
            if brand == 8:
                return "美的"
            if brand == 9:
                return "海尔"
            if brand == 10:
                return "LG"
            if brand == 13:
                return "三星"
            if brand == 14:
                return "奥克斯"
            if brand == 15:
                return "松下"
            if brand == 16:
                return "约克"
            if brand == 19:
                return "格力四代"
            if brand == 21:
                return "麦克维尔"
            if brand == 24:
                return "TCL"
            if brand == 25:
                return "志高"
            if brand == 26:
                return "天加"
            if brand == 35:
                return "约克T8600"
            if brand == 36:
                return "酷风"
            if brand == 37:
                return "约克青岛"
            if brand == 38:
                return "富士通"
            if brand == 39:
                return "三星(NotNASA_BMS)"
            if brand == 101:
                return "CH-Emerson"
            if brand == 102:
                return "CH-麦克维尔"
            if brand == 103:
                return "特灵"
            if brand == 255:
                return f"模拟器{proto}台"
            return ""

        # async with self._lock:
        url = f'{Endpoint.HOST.format(gateway=self.ip_addr)}{Endpoint.AC_BRAND}'
        resp = await self.async_get(url)
        if resp == None:
            return
        self.device_info['manufacturer'] = get_brand(resp['brand'], resp['proto'])

        url = f'{Endpoint.HOST.format(gateway=self.ip_addr)}{Endpoint.DEVICE_INFO}'
        resp = await self.async_get(url)
        if resp == None:
            return
        self.device_info['model'] = resp['model']
        self.device_info['model_id'] = resp['id']
        self.device_info['sw_version'] = resp['sw']

    def __get_socket(self) -> socket.socket:
        _LOGGER.debug("Opening socket to (%s, %s)", self.ip_addr, self.port)
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        if platform in ("linux", "linux2"):
            s.setsockopt(
                socket.IPPROTO_TCP, socket.TCP_KEEPIDLE, 1
            )  # pylint: disable=E1101
        if platform in ("darwin", "linux", "linux2"):
            s.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
            s.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPINTVL, 3)
            s.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPCNT, 5)
        s.connect((self.ip_addr, self.port))
        return s

    def open_socket(self):
        if self.sock:
            self.sock.close()
            self.sock = None
            time.sleep(1)

        self.sock = self.__get_socket()
        return self.sock

    def _get_data(self):
        if self.sock is None:
            self.open_socket()

        try:
            return self.sock.recv(SOCKET_BUFSIZE)

        except ConnectionResetError:
            _LOGGER.debug("Connection reset by peer")
            self.open_socket()

        except socket.timeout as e:
            _LOGGER.error("timeout error", exc_info=e)
            self.open_socket()

        except OSError as e:
            if e.errno == 9:  # when socket close, errorno 9 will raise
                _LOGGER.debug("OSError 9 raise, socket is closed")

            else:
                _LOGGER.error("unknown error when recv", exc_info=e)

            self.open_socket()

        except Exception as e:
            _LOGGER.error("unknown error when recv", exc_info=e)
            self.open_socket()

        return None

    def thread_main(self):
        while self._listening:
            data = self._get_data()
            if not data:
                continue
            self._listen_to_msg(data)

    def _listen_to_msg(self, data):
        _LOGGER.debug(f"recv data << {data.hex()}")
        def modbus_crc16(data):
            # data = bytes.fromhex(hex_string)
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

        def parse_tcp_payload(data):
            """Parse 16-hex payload from TCP data."""
            ac = {}
            if len(data) != 25:
                return ac
            if data[:8] != bytes([0x55, 0xaa, 0x00, 0x04, 0x02, 0x01, 0x00, 0x0f]):
                return ac
            if modbus_crc16(data[:23]) != data[23:]:
                return ac
            payload = data[8:-2]
            if sum(payload[:-1]) & 0xFF != int(payload[-1]):
                return ac
            # 仅支持单台空调的数据查询
            if payload[1] != 0x50 or len(payload) != 15:
                return ac
            ac[AC_Feature.GROUP] = int(payload[0])    # 猜测对应http协议的grp + 1
            ac[AC_Feature.AC_OUTDOOR] = int(payload[4])
            ac[AC_Feature.AC_INDOOR] = int(payload[5])
            ac[AC_Feature.STATE] = int(payload[6])
            ac[AC_Feature.TEMP_SET] = int(payload[7])
            ac[AC_Feature.MODE] = int(payload[8])
            ac[AC_Feature.FAN] = int(payload[9])
            ac[AC_Feature.TEMP_INDOOR] = int(payload[10])
            ac[AC_Feature.ALARM] = int(payload[11])
            _LOGGER.debug(f'get ac_data << {ac}')
            return ac

        ac = parse_tcp_payload(data)
        if ac != {}:
            ac_name = f"{ac[AC_Feature.GROUP]}_{ac[AC_Feature.AC_OUTDOOR]}_{ac[AC_Feature.AC_INDOOR]}"
            self.devices[ac_name].update(ac)
            if self._update_callbacks:
                self._notify_update_callbacks()

    def start_listen(self):
        """Start listening."""
        if self._listening:
            _LOGGER.info("Hub is listening")
            return True

        if self.sock is None:
            self.open_socket()

        self._listening = True
        thread = Thread(target=self.thread_main, args=())
        self._threads.append(thread)
        thread.daemon = True
        thread.start()
        _LOGGER.info("Start message listen thread %s", thread.ident)
        return True

    def stop_listen(self):
        _LOGGER.debug("Stopping hub")
        self._listening = False
        if self.sock:
            _LOGGER.info("Closing socket.")
            self.sock.close()
            self.sock = None

        for thread in self._threads:
            thread.join()
