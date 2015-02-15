"""Test posting notifications.

"""
import os
import unittest
import time
import logging
import subprocess

import requests

from cryptoassets.core.service.main import Service
from cryptoassets.core.app import ALL_SUBSYSTEMS

from ..configure import Configurator

from ..service import status

from . import testlogging
from . import testwarnings


_status_server_port = 18881


logger = logging.getLogger()


class ServiceTestCase(unittest.TestCase):
    """Test that we can wind up our helper service.
    """

    def setUp(self):
        testlogging.setup()
        testwarnings.begone()

    def prepare_config(self):
        """ """

        test_config = os.path.join(os.path.dirname(__file__), "service.config.yaml")
        self.assertTrue(os.path.exists(test_config), "Did not found {}".format(test_config))
        config = Configurator.prepare_yaml_file(test_config)

        # Dynamically patch in some system-wide globals,
        # so that shutting down test does not clash the next test
        config["status_server"]["port"] = self.get_next_status_server_port()
        config["coins"]["btc"]["backend"]["walletnotify"]["fname"] = "/tmp/cryptoassets-walletnotify-unittest-%d" % self.get_next_status_server_port()

        return config

    def tearDown(self):

        if not hasattr(self, "service"):
            return

        self.service.shutdown()

        # See that walletnotify handler cleans up itself
        walletnotify_handler = self.service.incoming_transaction_runnables["btc"]
        deadline = time.time() + 3
        while walletnotify_handler.running:
            self.assertLess(time.time(), deadline)

        # See that status server
        status_http_server = self.service.status_server
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
        """See that service starts and stops with bitcoind config."""

        config = self.prepare_config()

        self.service = Service(config, ALL_SUBSYSTEMS)
        # We should get one thread monitoring bitcoind walletnotify
        self.assertEqual(len(self.service.incoming_transaction_runnables), 1)

        # Check we read broadcast_period config
        self.assertEqual(self.service.broadcast_period, 60)

        self.service.start()

        walletnotify_handler = self.service.incoming_transaction_runnables["btc"]
        deadline = time.time() + 3
        while not walletnotify_handler.ready:
            self.assertLess(time.time(), deadline)

    def test_status(self):
        """See that the service broadcasts transactions when created."""

        config = self.prepare_config()

        self.service = service = Service(config, ALL_SUBSYSTEMS)
        self.service.setup_session()

        status_http_server = self.service.status_server
        self.assertIsNotNone(status_http_server)

        # Don't show wanted exceptions in the logging output
        status.logger.setLevel(logging.FATAL)

        try:

            service.start()

            # See that walletnotify handler cleans up itself
            deadline = time.time() + 3
            while not status_http_server.ready:
                self.assertLess(time.time(), deadline, "Status server did not start")

            for page in ("/", "/wallets", "/transactions", "/network_transactions", "/accounts", "/addresses"):
                report = requests.get("http://localhost:{}{}".format(config["status_server"]["port"], page))
                self.assertEqual(report.status_code, 200, "Failed page {}".format(page))

                # See we handle exception in status server code
                report = requests.get("http://localhost:{}/error".format(config["status_server"]["port"]))
                self.assertEqual(report.status_code, 500)

        finally:

            service.shutdown()

    def test_poll_network_transaction_confirmations(self):
        """See that the service broadcasts transactions when created."""

        config = self.prepare_config()

        self.service = service = Service(config, ALL_SUBSYSTEMS)
        self.service.setup_session()

        try:
            service.start()
            count = service.poll_network_transaction_confirmations()
            self.assertEqual(count, 1)
        finally:
            service.shutdown()

    def test_run_receive_scan(self):
        """See that we complete received transactions scan on startup."""

        config = self.prepare_config()

        self.service = service = Service(config, ALL_SUBSYSTEMS)
        self.service.setup_session()

        try:
            service.start()

            # My local test wallet is big...
            deadline = time.time() + 5 * 60
            while True:
                if service.receive_scan_thread:
                    if service.receive_scan_thread.complete:
                        break
                self.assertLess(time.time(), deadline, "oops could not rescan incoming transactions")

        finally:
            service.shutdown()


class StartupShutdownTestCase(unittest.TestCase):
    """Check that we start the service process and terminate it correctly. """

    def setUp(self):
        testlogging.setup()
        testwarnings.begone()
        self.test_config = os.path.join(os.path.dirname(__file__), "startstop.config.yaml")

        self.log_file = "/tmp/cryptoassets-startstop-test.log"

        if os.path.exists(self.log_file):
            os.unlink(self.log_file)

    def test_start_stop(self):
        """Start the service and stop it with SIGTERM signal."""

        # Initialize database
        logger.debug("Running initializedb")
        proc = subprocess.Popen(["cryptoassets-initialize-database", self.test_config], stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        proc.wait()
        if proc.returncode != 0:
            print("STDOUT:", proc.stdout.read().decode("utf-8"))
            print("STDERR:", proc.stderr.read().decode("utf-8"))

        self.assertEqual(proc.returncode, 0)

        # Start helper service
        logger.debug("Starting helper service")
        proc = subprocess.Popen(["cryptoassets-helper-service", self.test_config], stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        logger.debug("Running test service as pid %d", proc.pid)

        time.sleep(10)

        # See that we get log output
        self.assertTrue(os.path.exists(self.log_file))

        # See that we are still up after launch
        proc.poll()

        if proc.returncode:
            print("STDOUT:", proc.stdout.read().decode("utf-8"))
            print("STDERR:", proc.stderr.read().decode("utf-8"))

        self.assertIsNone(proc.returncode, "Helper service terminated itself, return code {}".format(proc.returncode))

        proc.terminate()
        time.sleep(16)

        proc.poll()

        if proc.returncode is None:
            print("STDOUT:", proc.stdout.read().decode("utf-8"))
            print("STDERR:", proc.stderr.read().decode("utf-8"))

        self.assertEqual(proc.returncode, 0, "Service was still running after SIGTERM and timeout")
