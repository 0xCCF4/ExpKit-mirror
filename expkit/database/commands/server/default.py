import textwrap
import threading
import urllib
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse

from expkit.base.architecture import Platform, Architecture
from expkit.base.command.base import CommandTemplate, CommandOptions, CommandArgumentCount
from expkit.base.logger import get_logger
from expkit.framework.database import register_command
from ipaddress import ip_address

from expkit.framework.parser import ConfigParser

LOGGER = get_logger(__name__)


@register_command
class ServerCommand(CommandTemplate):
    __instance = None

    def __new__(cls, *args, **kwargs):
        instance = super().__new__(cls, *args, **kwargs)
        cls.__instance = instance
        return instance

    def __init__(self):
        super().__init__(".server", CommandArgumentCount(0, 3), textwrap.dedent('''\
            Builds and serves an exploit on the fly when a client connects to the local server.
            '''), textwrap.dedent('''\
            Starts a webserver to build the exploit configuration defined in
            the config.json file on the fly whenever a request is received.
            The request must be a GET request with the following parameters:
            1. platform: The target platform (WINDOWS, LINUX, MACOS, ...).
            2. arch: The target architecture (i386, AMD64, ARM, ARM64, ...).
            3. target: The target artifact to build from the config.json file.
            4. token: The token to authenticate the request.
            If no token is set using the cli, the server will accept all requests.
            The response will the BASE64 encoded payload. If the payload is
            platform independent, the platform and arch parameters should be
            set to "DUMMY". An error will be signaled by returning no data.
            The server will listen on port 8080 and is bound to ip 0.0.0.0 by default.
            '''))

        self.__lock = threading.Lock()
        self.token = None

    @staticmethod
    def get_instance():
        return ServerCommand.__instance

    def get_pretty_description_header(self) -> str:
        return f"{super().get_pretty_description_header()} [port] [ip] [token]"

    def _execute_command(self, options: CommandOptions, *args) -> bool:
        with self.__lock:
            port = 8080
            ip = "0.0.0.0"
            self.token = None
            self.options = options

            if len(args) > 0:
                if str(port).isnumeric():
                    port = int(args[0])
                else:
                    LOGGER.critical(f"Invalid port: {args[0]}")
                    return False

            if len(args) > 1:
                ip = args[1]
                try:
                    ip = ip_address(ip)
                except ValueError:
                    LOGGER.critical(f"Invalid ip: {ip}")
                    return False

            if len(args) > 2:
                self.token = args[2]

            LOGGER.info(f"Starting server on {ip}:{port}")

            class RequestHandler(BaseHTTPRequestHandler):
                def do_GET(self):
                    ServerCommand.get_instance().handle_request(self)

            try:
                with HTTPServer((str(ip), port), RequestHandler) as httpd:
                    httpd.serve_forever()
            except KeyboardInterrupt:
                LOGGER.info("Stopping server")
                return True
            except OSError as e:
                LOGGER.critical(f"Port {port} is already in use.", e)
                return False

            raise NotImplementedError("Not implemented")

    def handle_request(self, handler: BaseHTTPRequestHandler):
        handler.protocol_version = "HTTP/1.1"
        url = urlparse(handler.path)
        query = urllib.parse.parse_qs(url.query)

        platform = query.get("platform", ["DUMMY"])[0]
        arch = query.get("arch", ["DUMMY"])[0]
        target = query.get("target", [None])[0]
        token = query.get("token", [None])[0]

        if token is not None and token != self.token:
            LOGGER.error(f"Invalid token: {token}")
            handler.send_response(401)
            handler.end_headers()
            return

        platform = Platform.get_platform_from_name(platform)
        if platform is Platform.UNKNOWN or not platform.is_single():
            LOGGER.error(f"Invalid platform: {platform}")
            handler.send_response(400)
            handler.end_headers()
            return

        arch = Architecture.get_architecture_from_name(arch)
        if arch is Architecture.UNKNOWN or not arch.is_single():
            LOGGER.error(f"Invalid architecture: {arch}")
            handler.send_response(400)
            handler.end_headers()
            return

        parser = ConfigParser()
        try:
            root = parser.parse(self.options.config, self.options.artifacts)
        except Exception as e:
            LOGGER.error(f"Failed to parse config file:", e)
            handler.send_response(500)
            handler.end_headers()
            return

        # TODO: validate stuff

        handler.send_response(200)
        handler.send_header("Content-type", "application/json")
        handler.send_header(f"Keep-Alive", f"timeout={60 * 30}, max=1")  # 30 minutes
        handler.end_headers()

        # TODO: build stuff

        # TODO: send stuff

        handler.wfile.write(b"Hello World !")