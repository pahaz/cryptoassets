import os
import threading
import unittest
from http.server import HTTPServer
from http.server import BaseHTTPRequestHandler

import requests

from ..utils import tunnel
from . import testwarnings


class DummyHandler(BaseHTTPRequestHandler):

    counter = 0

    def do_GET(self):
        self.send_response(200, "OK")
        self.end_headers()
        DummyHandler.counter += 1

    def log_message(self, format, *args):
        """Silent out default verbose output."""
        pass


class TestServer(threading.Thread):

    def __init__(self):
        threading.Thread.__init__(self)
        self.daemon = True
        self.httpd = None
        self.running = False

    def run(self):
        server_address = ('127.0.0.1', 10121)
        self.httpd = HTTPServer(server_address, DummyHandler)
        self.running = True
        self.httpd.serve_forever()

    def stop(self):
        if self.httpd:
            self.httpd.shutdown()


class NgrokTunnelTestCase(unittest.TestCase):
    """Test ngrok tunneling service."""

    def setUp(self):
        testwarnings.begone()

    def test_create_tunnel(self):
        """Test creating and retrieving wallet by name."""

        server = TestServer()
        server.start()
        ngrok = tunnel.NgrokTunnel(10121, os.environ["NGROK_AUTH_TOKEN"])
        url = ngrok.start()

        resp = requests.get(url)
        # We got 200 through ngrok
        self.assertEqual(resp.status_code, 200)
        # We actually hit our web server
        self.assertEqual(DummyHandler.counter, 1)

        ngrok.stop()
