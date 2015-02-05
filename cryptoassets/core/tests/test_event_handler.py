"""Test posting notifications.

"""
import io
import os
import stat
import unittest
import json
import threading
import requests
import time
from decimal import Decimal
from http.server import HTTPServer
from http.server import BaseHTTPRequestHandler

from ..app import CryptoAssetsApp
from ..app import Subsystem
from ..configure import Configurator

from . import testlogging
from . import testwarnings
from ..utils import danglingthreads


testlogging.setup()


SAMPLE_SCRIPT_PATH = "/tmp/cryptoassets-test_notifier.sh"

SAMPLE_SCRIPT = """#/bin/sh
echo Foo
echo $0
echo $CRYPTOASSETS_EVENT_NAME
echo $CRYPTOASSETS_EVENT_DATA

echo $CRYPTOASSETS_EVENT_DATA > /tmp/cryptoassets-test_notifier
"""


class ScriptNotificationTestCase(unittest.TestCase):
    """
    """

    def setUp(self):

        self.app = CryptoAssetsApp([Subsystem.event_handler_registry])
        self.configurator = Configurator(self.app)

        # Create a test script
        with io.open(SAMPLE_SCRIPT_PATH, "wt") as f:
            f.write(SAMPLE_SCRIPT)

        st = os.stat(SAMPLE_SCRIPT_PATH)
        os.chmod(SAMPLE_SCRIPT_PATH, st.st_mode | stat.S_IEXEC)

    def tearDown(self):
        danglingthreads.check_dangling_threads()

    def test_notify(self):
        """ Do a succesful notification test.
        """
        config = {
            "test_script": {
                "class": "cryptoassets.core.event.script.ScriptEventHandler",
                "script": SAMPLE_SCRIPT_PATH,
                "log_output": True
            }
        }
        event_handler_registry = self.configurator.setup_event_handlers(config)

        event_handler_registry.trigger("foobar", {"test": "abc"})

        with io.open("/tmp/cryptoassets-test_notifier", "rt") as f:
            data = json.load(f)
            self.assertEqual(data["test"], "abc")


_cb_data = None


def global_recording_callback(event_name, data):
    global _cb_data
    _cb_data = data


class PythonNotificationTestCase(unittest.TestCase):
    """Test in-process Python notifications.
    """

    def setUp(self):
        self.app = CryptoAssetsApp([Subsystem.event_handler_registry])
        self.configurator = Configurator(self.app)

    def tearDown(self):
        danglingthreads.check_dangling_threads()

    def test_notify(self):
        """ Do a succesful notification test.
        """
        config = {
            "test_python": {
                "class": "cryptoassets.core.event.python.InProcessEventHandler",
                "callback": "cryptoassets.core.tests.test_event_handler.global_recording_callback",
            }
        }
        event_handler_registry = self.configurator.setup_event_handlers(config)

        event_handler_registry.trigger("foobar", {"test": "abc"})

        self.assertEqual(_cb_data["test"], "abc")


class DummyHandler(BaseHTTPRequestHandler):

    counter = 0

    def do_POST(self):
        self.send_response(200, "OK")
        self.end_headers()
        DummyHandler.counter += 1

    def log_message(self, format, *args):
        pass


class TestServer(threading.Thread):

    def __init__(self):
        threading.Thread.__init__(self)
        self.daemon = True
        self.httpd = None
        self.running = False

    def run(self):
        server_address = ('127.0.0.1', 10000)
        self.httpd = HTTPServer(server_address, DummyHandler)
        self.running = True
        self.httpd.serve_forever()

    def stop(self):
        if self.httpd:
            self.httpd.shutdown()


class HTTPNotificationTestCase(unittest.TestCase):
    """Test sending out HTTP notifications.
    """

    def setUp(self):
        self.app = CryptoAssetsApp([Subsystem.event_handler_registry])
        self.configurator = Configurator(self.app)

    def tearDown(self):
        danglingthreads.check_dangling_threads()

    def test_notify(self):
        """ Do a succesful notification test.
        """

        config = {
            "test_script": {
                "class": "cryptoassets.core.event.http.HTTPEventHandler",
                "url": "http://localhost:10000"
            }
        }
        event_handler_registry = self.configurator.setup_event_handlers(config)

        server = TestServer()
        try:
            server.start()

            # Wait until walletnotifier has set up the named pipe
            deadline = time.time() + 3
            while not server.running:
                time.sleep(0.1)
                self.assertLess(time.time(), deadline, "TestServer never become ready")

            event_handler_registry.trigger("foobar", {"test": "abc", "test2": Decimal("1.0")})
        finally:
            server.stop()

        # We did 1 succesful HTTP request
        self.assertEqual(DummyHandler.counter, 1)
