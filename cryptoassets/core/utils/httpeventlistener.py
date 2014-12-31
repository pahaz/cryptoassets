"""Create ad-hoc HTTP server to listen to incoming cryptoassets.core events in your application"""

import json
import threading
import atexit
import urllib
import logging
from http.server import HTTPServer
from http.server import BaseHTTPRequestHandler

from cgi import parse_header
from cgi import parse_multipart
from urllib.parse import parse_qs


logger = logging.getLogger(__name__)


class CryptoassetsServiceRequestHandler(BaseHTTPRequestHandler):
    """Very crude HTTP POST processor.

    Extra txid from the POST request.
    """
    def do_POST(self):

        try:
            ctype, pdict = parse_header(self.headers['content-type'])
            if ctype == 'multipart/form-data':
                postvars = parse_multipart(self.rfile, pdict)
            elif ctype == 'application/x-www-form-urlencoded':
                length = int(self.headers['content-length'])
                postvars = parse_qs(self.rfile.read(length), keep_blank_values=1)
            else:
                postvars = {}

            event_name = postvars[b"event_name"][0].decode("utf-8")

            logger.debug("Handling incoming event %s", event_name)

            data = postvars[b"data"][0].decode("utf-8")
            data = json.loads(data)
            self.server.func(event_name, data)

            self.send_response(200, "OK")
            self.end_headers()
            return ""
        except Exception as e:
            logger.error("Error handling incoming event")
            logger.exception(e)
            self.send_response(500, "Internal server error")
            self.end_headers()
            raise e


class SimpleHTTPEventListenerThread(threading.Thread):

    def __init__(self, ip, port, func):
        """
        :param func: The event handling callback function

        :param ip: IP address / host to bind

        :param port: Port to bind
        """

        self.func = func

        #: HTTP server instance we are running
        self.httpd = None

        server_address = (ip, port)

        try:
            self.httpd = HTTPServer(server_address, CryptoassetsServiceRequestHandler)

            # XXX: More explicitly pass this around?
            self.httpd.func = func
        except OSError as e:
            raise RuntimeError("Could not start cryptoassets server HTTP event listener at {}:{}".format(self.ip, self.port)) from e

        self.running = False

        threading.Thread.__init__(self)

    def run(self):
        self.running = True
        self.httpd.serve_forever()

    def stop(self):
        self.running = False
        if self.httpd:
            self.httpd.shutdown()


def simple_http_event_listener(config, daemon=True):
    """Convenience decorator to open HTTP event listever for configured cryptoassets service.

    Opens a new HTTP server running a background thread. Whenever cryptoassets helper service posts a new event, it will be received by this HTTP server which then executes the event in your application context.

    This can be used only once per application, so you need to dispatch listened events to your own event handling funcions in one singleton handler.

    :param config: Full cryptoassets configuration as Python dict

    :param func:  The event handling callback function, ``callback(event_name, data_dict)`.

    :param daemon: Should the server be started as a daemon thread (does not prevent Python application quitting unless explictly stopped)
    """

    def actual_decorator(func):

        assert type(config) == dict

        # Exract status server address from the configuration
        notify_config = config.get("notify")

        if not notify_config:
            raise RuntimeError("Could not get the configuration for HTTP event server")

        # Get first HTTP event handling entty from the config and grab it's IP and URL there
        host = port = None
        for data in notify_config.values():
            if data["class"] == "cryptoassets.core.notify.http.HTTPNotifier":
                url = urllib.parse.urlparse(data["url"])
                port = url.port
                host = url.hostname

                assert url.path in ("/", ""), "Simple HTTP Event listener doesn't support URLs with paths, your path was {}".format(url.path)

        if not host:
            raise RuntimeError("Could not find HTTP event server configuration in cryptoassets config")

        server = SimpleHTTPEventListenerThread(host, port, func)
        server.daemon = daemon
        server.start()

        def handle_cleanup():
            server.stop()

        atexit.register(handle_cleanup)

        func.http_server = server

        return func

    return actual_decorator