import unittest
import requests
import time

from ..utils.httpeventlistener import cryptoservice_http_event_listener

from . import testlogging
from . import testwarnings


_got_data = None


class SimpleHTTPEventListenerTestCase(unittest.TestCase):
    """Check that our simple HTTP event listener function decorator works.
    """

    def setUp(self):
        testwarnings.begone()
        testlogging.setup()

    def test_decorate(self):
        """ Do a succesful notification test.
        """

        config = {
            "notify": {
                "test_script": {
                    "class": "cryptoassets.core.notify.http.HTTPNotifier",
                    "url": "http://localhost:10000"
                }
            }
        }

        @cryptoservice_http_event_listener(config, daemon=False)
        def myfunc(event, data):
            global _got_data
            _got_data = data

        server = myfunc.http_server

        try:

            deadline = time.time() + 1
            while not server.running:
                time.sleep(0.1)
                self.assertLess(time.time(), deadline, "Event capture HTTP server never woke up")

            requests.post("http://localhost:10000", {
                "event_name": "myfoobar",
                "data": '{"foo":"bar"}',
                })

            deadline = time.time() + 1
            while not server.running:
                time.sleep(0.1)
                if _got_data:
                    break
                self.assertLess(time.time(), deadline, "Event capture HTTP server never woke up")

            self.assertEqual(_got_data, {"foo": "bar"})

        finally:

            server.stop()
