"""Test posting notifications.

"""
import io
import os
import stat
import unittest
import json
import threading
import warnings
import time
import faulthandler

import requests

from cryptoassets.core.service.main import Service

from .. import configure
from ..notify import notify
from . import testlogging

from ..service import status

testlogging.setup()


_status_server_port = 18881


class ServiceTestCase(unittest.TestCase):
    """Test that we can wind up our helper service.
    """

    def setUp(self):
        # /Users/mikko/code/cryptoassets/venv/lib/python3.4/site-packages/tzlocal/darwin.py:8: ResourceWarning: unclosed file <_io.TextIOWrapper name=4 encoding='US-ASCII'>
        warnings.filterwarnings("ignore", category=ResourceWarning)  # noqa

    def prepare_config(self):
        """ """

        test_config = os.path.join(os.path.dirname(__file__), "service.config.yaml")
        self.assertTrue(os.path.exists(test_config), "Did not found {}".format(test_config))
        config = configure.prepare_yaml_file(test_config)

        config["status-server"]["port"] = self.get_next_status_server_port()
        config["backends"]["btc"]["walletnotify"]["fname"] = "/tmp/cryptoassets-walletnotify-unittest-%d" % self.get_next_status_server_port()

        return config

    def tearDown(self):

        self.service.shutdown()

        # See that walletnotify handler cleans up itself
        walletnotify_handler = self.service.incoming_transaction_runnables["btc"]
        deadline = time.time() + 3
        while walletnotify_handler.running:
            self.assertLess(time.time(), deadline)

        # See that status server
        status_http_server = status.status_http_server
        deadline = time.time() + 3
        if status_http_server:
            while status_http_server.running:
                self.assertLess(time.time(), deadline)

        # Use this to spotted still alive threads after service shutdown
        # time.sleep(0.1)
        # faulthandler.dump_traceback()

    def get_next_status_server_port(self):
        """ Avoid port clashes between tests. """
        global _status_server_port
        _status_server_port += 1
        return _status_server_port

    def test_start_shutdown_service(self):
        """See that service starts and stops with bitcoind config.
        """
        config = self.prepare_config()

        self.service = service = Service(config)
        # We should get one thread monitoring bitcoind walletnotify
        self.assertEqual(len(service.incoming_transaction_runnables), 1)

        service.start()

        walletnotify_handler = service.incoming_transaction_runnables["btc"]
        deadline = time.time() + 3
        while not walletnotify_handler.ready:
            self.assertLess(time.time(), deadline)

    def test_status(self):
        """See that the service broadcasts transactions when created."""

        config = self.prepare_config()

        self.service = service = Service(config)

        status_http_server = status.status_http_server

        try:

            service.start()

            # See that walletnotify handler cleans up itself
            deadline = time.time() + 3
            while not status_http_server.ready:
                self.assertLess(time.time(), deadline, "Status server did not start")

            report = requests.get("http://localhost:{}/".format(config["status-server"]["port"]))
            self.assertEqual(report.status_code, 200)
            service.shutdown()

        finally:

            service.shutdown()
