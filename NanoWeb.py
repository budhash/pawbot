import uasyncio as asyncio
import uerrno
import network
import socket
import ure
import time
import binascii
import ujson as json

class CredManager:
    def __init__(self, storage = 'wifi.dat'):
        self.storage = storage
        self.credentials = {}
        self.load()

    def load(self) -> None:
        try:
            with open(self.storage, 'r') as f:
                self.credentials = json.load(f)
        except Exception:
            self.credentials = {}

    async def save(self) -> None:
        with open(self.storage, 'w') as f:
            json.dump(self.credentials, f)

    def add(self, ssid: str, password: str) -> None:
        self.credentials[ssid] = password
        self.save()

    def remove(self, ssid: str) -> None:
        if ssid in self.credentials:
            del self.credentials[ssid]
            self.save()

    def clear(self) -> None:
        self.credentials = {}
        self.save()

    def get(self, ssid: str) -> Tuple[str, str]:
        password = self.credentials.get(ssid)
        return (ssid, password) if password else None

    def list(self) -> List[Tuple[str, str]]:
        return [(ssid, password) for ssid, password in self.credentials.items()]


class ConnectionManager:
    AP_PORT = 80
    AP_SSID = "NanoWeb"
    AP_PASSWORD = "password"
    AP_AUTHMODE = 3  # WPA2

    def __init__(self, conn_timeout_sec: int = 10000, ap_port: int = AP_PORT, ap_ssid: str = AP_SSID, ap_password: str = AP_PASSWORD, ap_authmode: int = AP_AUTHMODE):
        print("initializing connection manager...")
        self.ap_port = ap_port
        self.ap_ssid = ap_ssid
        self.ap_password = ap_password
        self.ap_authmode = ap_authmode
        self.wlan_ap = network.WLAN(network.AP_IF)
        self.wlan_sta = network.WLAN(network.STA_IF)
        self.cred_manager = CredManager()
        self.conn_timeout_sec = conn_timeout_sec

    async def boot(self, event_loop) -> bool:
        print("starting boot sequence...")
        await self.disconnect()
        if not await self.connected():
            print("trying to auto connect...")
            success = await self.auto_connect()
            return success
        else:
            return True
    
    def __connected(self) -> bool:
        """Checks if the device is connected to a network

        Returns:
            bool: True if connected, False otherwise
        """
        return self.wlan_sta.isconnected()
        
    async def connected(self, max_retries = 3, delay_ms = 1000) -> bool:
        """Asynchronously checks if the device is connected to a network
        It retries the check up to 3 times with a delay of 1 second between attempts

        Returns:
            bool: True if connected after retries, False otherwise
        """
        success, _ = await retry_until(
            predicate=lambda result: result == True,
            action=self.__connected,
            max_retries=max_retries,
            delay_ms=delay_ms
        )
        return success

    def ifconfig(self) -> Tuple[str, str, str, str]:
        if self.__connected():
            ip, subnet, gateway, dns = self.wlan_sta.ifconfig()
            return (ip, subnet, gateway, dns)
        else:
            return ("", "", "", "")
    
    def scan_available_networks(self) -> List[Tuple[str, str, int]]:
        """Scans for available networks and returns a list of networks sorted by signal strength

        Returns:
            list: A list of tuples. Each tuple contains the SSID (str), BSSID (str, MAC address), hidden (bool) and signal strength (int, RSSI value) of a network
        """
        networks = self.wlan_sta.scan()
        sorted_networks = sorted(networks, key=lambda network: network[3], reverse=True)
        return [
            (ssid.decode('utf-8'), ':'.join(['{:02x}'.format(b) for b in bssid]), rssi)
            for ssid, bssid, _, rssi, _, _ in sorted_networks
            if ssid.decode('utf-8') and self.is_printable(ssid.decode('utf-8'))
            ]

    async def connect(self, ssid: str, password: str, timeout_ms: int = 10000) -> bool:
        """Connects to a WiFi network

        Args:
            ssid (str): The SSID of the WiFi network
            password (str): The password of the WiFi network
            timeout (int, optional): The number of seconds to wait before giving up. Defaults to 10

        Returns:
            bool: True if the connection was successful, False otherwise
        """
        print(f"attempting to connect to network: {ssid}...")
        delay_ms = 1000
        self.wlan_sta.active(True)
        self.wlan_sta.connect(ssid, password)
        
        if not await self.connected(max_retries = timeout_ms/delay_ms, delay_ms = delay_ms):
            # todo - map status to enum
            # https://docs.micropython.org/en/latest/library/network.WLAN.html
            status = self.wlan_sta.status()
            print(f"failed to connect to the network: {ssid} | status: {status}")
            self.wlan_sta.active(False)
            return False
        nw_config = self.wlan_sta.ifconfig()
        print(f"connected to network: {ssid}")
        print(f"network: {nw_config}")
        return True

    async def auto_connect(self) -> bool:
        # get the list of network credentials
        credentials = self.cred_manager.list()
        # if no credentials were found, return immediately
        if not credentials:
            print("no credentials found - unable to auto-connect")
            return False
        for ssid, password in credentials:
            success = await self.connect(ssid, password)
            if success:
                return True
        print("could not connect to any network.")
        return False

    async def disconnect(self, timeout_ms: int = 10000) -> bool:
        if self.__connected():
            print(f"attempting to disconnect...")
            self.wlan_sta.disconnect()
            success, _ = await retry_until(
                predicate=lambda result: result == False,
                action=self.__connected,
                max_retries=3,
                delay_ms=1000
            )
            return success
        else:
            print(f"not connected...")
            return True
    
    def disable_network(self) -> None:
        self.wlan_sta.active(False)
        
    def enable_ap(self) -> str:
        print(f"enabling access point...")
        self.wlan_ap.active(False)
        self.wlan_ap.config(essid=self.ap_ssid, password=self.ap_password)
        self.wlan_ap.active(True)
        ip_address, _, _, _ = self.wlan_ap.ifconfig()
        print(f"enabled: ssid: {self.ap_ssid}, pass: {self.ap_password}, ip: {ip_address}")
        return ip_address
    
    def disable_ap(self) -> None:
        print(f"disabling access point...")
        self.wlan_ap.active(False)
    
    @staticmethod
    def is_printable(s: str) -> bool:
        return all(31 < ord(c) < 127 for c in s)

    def initialize_access_point(self, event_loop) -> Tuple[str, str, str]:
        ip_address = self.enable_ap()
        self.start_access_portal(event_loop)
        return (self.ap_ssid, self.ap_password, ip_address)
    
    def start_access_portal(self, event_loop) -> None:
        print(f"starting access portal...")
        naw = Nanoweb(80)
        naw.routes = {
            '/ping': self.__ping,
            '/wifi/scan': self.__wifi_scan,
            '/wifi/add': self.__wifi_add,
            '/wifi/list': self.__wifi_list,
            '/wifi/clear': self.__wifi_clear,
            '/wifi/connect': self.__wifi_connect,
        }
        event_loop.create_task(naw.run())
        print(f"access portal started")

    async def __ping(self, request) -> None:
        print("Handler: ping")
        await json_write(request, '{"status": "pong"}')
        
    async def __wifi_scan(self, request) -> None:
        print("Handler: /wifi/scan")
        try:
            networks = [{"ssid": ssid, "mac": mac, "rssi": rssi}
                    for ssid, mac, rssi in self.scan_available_networks()]
            response_json = json.dumps({"networks": networks})
            await json_write(request, response_json)
        except Exception as e:
            print(e)
            await json_error(request, 500, "Internal Server Error", "Internal Server Error")

    async def __wifi_add(self, request) -> None:
        print("Handler: /wifi/add")
        try:
            content = await json_read(request)
            ssid = content.get('ssid')
            password = content.get('password')

            # validation
            if not ssid or not password:
                await json_error(request, 400, "Bad Request", "both ssid and password must be provided")
                return

            self.cred_manager.add(ssid, password)
            await self.cred_manager.save()
            await json_write(request, json.dumps({"status": "credentials saved"}))
        except Exception as e:
            print(e)
            await json_error(request, 500, "Internal Server Error", "Internal Server Error")
    
    async def __wifi_list(self, request) -> None:
        print("Handler: wifi/list")
        try:
            credentials = [{"ssid": ssid, "password": "****"}
                    for ssid, password in self.cred_manager.list()]
            response_json = json.dumps({"credentials": credentials})
            await json_write(request, response_json)
        except Exception as e:
            print(e)
            await json_error(request, 500, "Internal Server Error", "Internal Server Error")

    async def __wifi_clear(self, request) -> None:
        print("Handler: /wifi/clear")
        try:
            self.cred_manager.clear()
            await self.cred_manager.save()
            await json_write(request, json.dumps({"status": "credentials cleared"}))
        except Exception as e:
            print(e)
            await json_error(request, 500, "Internal Server Error", "Internal Server Error")

    async def __wifi_connect(self, request) -> None:
        print("Handler: /wifi/connect")
        try:
            success = await self.auto_connect()
            if success:
                await json_write(request, json.dumps({"status": "success"}))
                # todo : drop the connection here
                self.disable_ap()
            else:
               await json_write(request, json.dumps({"status": "failed"})) 
        except Exception as e:
            print(e)
            await json_error(request, 500, "Internal Server Error", "Internal Server Error")
            
class HttpError(Exception):
    pass

class Request:
    url = ""
    method = ""
    headers = {}
    route = ""
    read = None
    write = None
    close = None

    def __init__(self):
        self.url = ""
        self.method = ""
        self.headers = {}
        self.route = ""
        self.read = None
        self.write = None
        self.close = None
    
async def write(request, data):
    await request.write(data.encode('ISO-8859-1') if type(data) == str else data)

async def read(request):
    content = ""
    if 'Content-Length' in request.headers:
        length = int(request.headers['Content-Length'])
        try: 
            content = await request.read(length)
        except Exception as e:
            print(e)
    return content

async def error(request, code, reason):
    await request.write("HTTP/1.1 %s %s\r\n\r\n" % (code, reason))
    await request.write("<h1>%s</h1>" % (reason))

async def json_read(request):
    content = await read(request)
    try:
        return json.loads(content)
    except Exception as e:
        print(e)
        return json.loads("{}")

async def json_write(request, response_json):
    await request.write("HTTP/1.1 200 OK\r\n")
    await request.write("Content-Type: application/json\r\n\r\n")
    await request.write(response_json)

async def json_error(request, code, reason, message):
    await request.write(f"HTTP/1.1 {code} {reason}\r\n")
    await request.write("Content-Type: application/json\r\n\r\n")
    await request.write(json.dumps({"error": message}))

async def send_file(request, filename, segment=64, binary=False):
    try:
        with open(filename, 'rb' if binary else 'r') as f:
            while True:
                data = f.read(segment)
                if not data:
                    break
                await request.write(data)
    except OSError as e:
        if e.args[0] != uerrno.ENOENT:
            raise
        raise HttpError(request, 404, "File Not Found")


class Nanoweb:

    extract_headers = ('Authorization', 'Content-Length', 'Content-Type')
    headers = {}

    routes = {}
    assets_extensions = ('html', 'css', 'js')

    callback_request = None
    callback_error = staticmethod(error)

    STATIC_DIR = './'
    INDEX_FILE = STATIC_DIR + 'index.html'

    def __init__(self, port=80, address='0.0.0.0'):
        self.port = port
        self.address = address

    def route(self, route):
        """Route decorator"""
        def decorator(func):
            self.routes[route] = func
            return func
        return decorator

    async def generate_output(self, request, handler):
        """Generate output from handler

        `handler` can be :
         * dict representing the template context
         * string, considered as a path to a file
         * tuple where the first item is filename and the second
           is the template context
         * callable, the output of which is sent to the client
        """
        while True:
            if isinstance(handler, dict):
                handler = (request.url, handler)

            if isinstance(handler, str):
                await write(request, "HTTP/1.1 200 OK\r\n\r\n")
                await send_file(request, handler)
            elif isinstance(handler, tuple):
                await write(request, "HTTP/1.1 200 OK\r\n\r\n")
                filename, context = handler
                context = context() if callable(context) else context
                try:
                    with open(filename, "r") as f:
                        for l in f:
                            await write(request, l.format(**context))
                except OSError as e:
                    if e.args[0] != uerrno.ENOENT:
                        raise
                    raise HttpError(request, 404, "File Not Found")
            else:
                handler = await handler(request)
                if handler:
                    # handler can returns data that can be fed back
                    # to the input of the function
                    continue
            break

    async def handle(self, reader, writer):
        items = await reader.readline()
        items = items.decode('ascii').split()
        if len(items) != 3:
            return

        request = Request()
        request.read = reader.read
        request.write = writer.awrite
        request.close = writer.aclose

        request.method, request.url, version = items

        try:
            try:
                if version not in ("HTTP/1.0", "HTTP/1.1"):
                    raise HttpError(request, 505, "Version Not Supported")

                while True:
                    items = await reader.readline()
                    items = items.decode('ascii').split(":", 1)

                    if len(items) == 2:
                        header, value = items
                        value = value.strip()

                        if header in self.extract_headers:
                            request.headers[header] = value
                    elif len(items) == 1:
                        break

                if self.callback_request:
                    self.callback_request(request)

                if request.url in self.routes:
                    # 1. If current url exists in routes
                    request.route = request.url
                    await self.generate_output(request,
                                               self.routes[request.url])
                else:
                    # 2. Search url in routes with wildcard
                    for route, handler in self.routes.items():
                        if route == request.url \
                            or (route[-1] == '*' and
                                request.url.startswith(route[:-1])):
                            request.route = route
                            await self.generate_output(request, handler)
                            break
                    else:
                        # 3. Try to load index file
                        if request.url in ('', '/'):
                            await send_file(request, self.INDEX_FILE)
                        else:
                            # 4. Current url have an assets extension ?
                            for extension in self.assets_extensions:
                                if request.url.endswith('.' + extension):
                                    await send_file(
                                        request,
                                        '%s/%s' % (
                                            self.STATIC_DIR,
                                            request.url,
                                        ),
                                        binary=True,
                                    )
                                    break
                            else:
                                raise HttpError(request, 404, "File Not Found")
            except HttpError as e:
                request, code, message = e.args
                await self.callback_error(request, code, message)
        except OSError as e:
            # Skip ECONNRESET error (client abort request)
            if e.args[0] != uerrno.ECONNRESET:
                raise
        finally:
            await writer.aclose()

    async def run(self):
        return await asyncio.start_server(self.handle, self.address, self.port)

def get_time():
    uptime_s = int(time.ticks_ms() / 1000)
    uptime_h = int(uptime_s / 3600)
    uptime_m = int(uptime_s / 60)
    uptime_m = uptime_m % 60
    uptime_s = uptime_s % 60
    return (
        '{}-{:02d}-{:02d} {:02d}:{:02d}:{:02d}'.format(*time.localtime()),
        '{:02d}h {:02d}:{:02d}'.format(uptime_h, uptime_m, uptime_s),
    )

async def retry_until(predicate, action, max_retries=3, delay_ms=500):
    for i in range(max_retries):
        result = action()
        #print(f"Attempt {i+1} result: {result}")
        if predicate(result):
            return True, result
        await asyncio.sleep_ms(delay_ms)
    #print("Max retries reached. Condition not fulfilled.")
    return False, None
        
#async def main():
#    event_loop = asyncio.get_event_loop()
#    manager = ConnectionManager()
#    await manager.boot(event_loop)
#    event_loop.run_forever()
#    
#asyncio.run(main())

