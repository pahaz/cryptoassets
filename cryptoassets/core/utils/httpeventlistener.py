"""Convenience decorator to open HTTP event listever for configured cryptoassets service.

Opens a new HTTP server running a background thread. Whenever cryptoassets helper service posts a new event, it will be received by this HTTP server which then executes the event in your application context.

This can be used only once per application, so you need to dispatch listened events to your own event handling funcions in one singleton handler.

The callback receives two arguments, ``event_name`` (string) and ``data`` (dict). Data payload depends on the event type.

Example::

    app = CryptoAssetsApp()

    # This will load the configuration file for the cryptoassets framework
    configurer = Configurator(app)
    configurer.load_yaml_file("cryptoassets-settings.yaml")

    @simple_http_event_listener(configurer.config)
    def my_event_callback(event_name, data):
        if event_name == "txupdate":
            print("Got transaction update {}".format(data))

"""

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

    def log_request(self, code=None, size=None):
        logger.debug("HTTP %d", code)

    def do_POST(self):

        try:
            # http://stackoverflow.com/a/12731208/315168
            # Extract and print the contents of the POST
            length = int(self.headers['Content-Length'])
            post_data = parse_qs(self.rfile.read(length).decode('utf-8'))

            if "data" not in post_data:
                raise RuntimeError("Incoming POST did not contain data field: {}".format(post_data))

            event_name = post_data["event_name"][0]
            data = post_data["data"][0]

            logger.debug("Handling incoming event %s", event_name)

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


class EventCaptureHTTPServer(HTTPServer):
    """HTTP Server responsing to event HTTP POST notifications."""


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
            self.httpd = EventCaptureHTTPServer(server_address, CryptoassetsServiceRequestHandler)

            # XXX: More explicitly pass this around?
            self.httpd.func = func
        except OSError as e:
            raise RuntimeError("Could not start cryptoassets server HTTP event listener at {}:{}".format(ip, port)) from e

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
    """Function decorator to make the target function to retrieve events from cryptoassets helper service over HTTP event callback.

    You can also call this manually from command line from testing::

        curl --data 'event_name=txupdate&data={"transaction_type":"broadcast","address":"x","confirmations":2,"txid":"foobar"}' http://127.0.0.1:10000

    :param config: *cryptoassets.core* app configuration as Python dict. We'll extract the information which port and IP to listen to on HTTP server from there.

    :param func:  The event handling callback function, ``callback(event_name, data_dict)``.

    :param daemon: Should the server be started as a daemon thread (does not prevent Python application quitting unless explictly stopped)
    """

    def actual_decorator(func):

        assert type(config) == dict

        # Exract status server address from the configuration
        notify_config = config.get("events")

        if not notify_config:
            raise RuntimeError("Could not get the configuration for cryptoassets service process events")

        # Get first HTTP event handling entty from the config and grab it's IP and URL there
        host = port = None
        for data in notify_config.values():
            if data["class"] == "cryptoassets.core.event.http.HTTPEventHandler":
                url = urllib.parse.urlparse(data["url"])
                port = url.port
                host = url.hostname

                assert url.path in ("/", ""), "Simple HTTP Event listener doesn't support URLs with paths, your path was {}".format(url.path)

                break

        else:
            raise RuntimeError("Could not find cryptoassets.core.event.http.HTTPEventHandler configuration in cryptoassets config")

        server = SimpleHTTPEventListenerThread(host, port, func)
        server.daemon = daemon
        server.start()

        def handle_cleanup():
            server.stop()

        atexit.register(handle_cleanup)

        func.http_server = server

        return func

    return actual_decorator

__all__ = [simple_http_event_listener]
