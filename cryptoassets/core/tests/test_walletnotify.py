import os
import time
import unittest
import subprocess

from unittest.mock import patch

import redis

from ..backend.pipewalletnotify import PipedWalletNotifyHandler
from ..backend.httpwalletnotify import HTTPWalletNotifyHandler
from ..backend.httpwalletnotify import WalletNotifyRequestHandler
from ..backend.rediswalletnotify import RedisWalletNotifyHandler

from . import testlogging
from . import testwarnings
from ..utils import danglingthreads

WALLETNOTIFY_PIPE = "/tmp/cryptoassets-unittest-walletnotify-pipe"


class WalletNotifyTestCase(unittest.TestCase):
    """Test bitcoind walletnotify handlers..
    """

    def setUp(self):
        testlogging.setup()
        testwarnings.begone()

    def tearDown(self):
        danglingthreads.check_dangling_threads()

    def test_piped_walletnotify(self):
        """Check that we receive txids through the named pipe."""

        # Generate unique walletnotify filenames for each test, so that when multiple tests are running, one thread stopping in teardown doesn't unlink the pipe of the previous test
        pipe_fname = WALLETNOTIFY_PIPE + "_test_piped_walletnotify"

        # Patch handle_tx_update() to see it gets called when we write something to the pipe
        with patch.object(PipedWalletNotifyHandler, 'handle_tx_update', return_value=None) as mock_method:

            self.walletnotify_pipe = PipedWalletNotifyHandler(None, pipe_fname)
            self.walletnotify_pipe.start()

            # Wait until walletnotifier has set up the named pipe
            deadline = time.time() + 3
            while not self.walletnotify_pipe.ready:
                time.sleep(0.1)
                self.assertLess(time.time(), deadline, "PipedWalletNotifyHandler never become ready")

            self.assertTrue(self.walletnotify_pipe.is_alive())
            self.assertTrue(os.path.exists(pipe_fname))

            subprocess.call("echo faketransactionid >> {}".format(pipe_fname), shell=True)
            time.sleep(0.1)  # Let walletnotify thread to pick it up

            mock_method.assert_called_with("faketransactionid")

        self.walletnotify_pipe.stop()

    def test_http_walletnotify(self):
        """Check that we receive txids through HTTP server."""

        self.walletnotify_server = HTTPWalletNotifyHandler(None, ip="127.0.0.1", port=9991)

        try:

            # Generate unique walletnotify filenames for each test, so that when multiple tests are running, one thread stopping in teardown doesn't unlink the pipe of the previous test
            # Patch handle_tx_update() to see it gets called when we write something to the pipe
            with patch.object(WalletNotifyRequestHandler, 'handle_tx_update', return_value=None) as mock_method:

                self.walletnotify_server.start()

                # Wait until walletnotifier has set up the named pipe
                deadline = time.time() + 3
                while not self.walletnotify_server.ready:
                    time.sleep(0.1)
                    self.assertLess(time.time(), deadline, "HTTPWalletNotifyHandler never become ready")

                self.assertTrue(self.walletnotify_server.is_alive())

                subprocess.call("curl --data 'txid=faketransactionid' http://127.0.0.1:9991", shell=True)
                time.sleep(0.1)  # Let walletnotify thread to pick it up

                mock_method.assert_called_with("faketransactionid")

        finally:

            self.walletnotify_server.stop()

    def test_redis_walletnotify(self):
        """Check that we receive txids through HTTP server."""

        self.walletnotify_server = RedisWalletNotifyHandler(None, "localhost")

        try:

            # Generate unique walletnotify filenames for each test, so that when multiple tests are running, one thread stopping in teardown doesn't unlink the pipe of the previous test
            # Patch handle_tx_update() to see it gets called when we write something to the pipe
            with patch.object(RedisWalletNotifyHandler, 'handle_tx_update', return_value=None) as mock_method:

                self.walletnotify_server.start()

                # Wait until walletnotifier has set up the named pipe
                deadline = time.time() + 3
                while not self.walletnotify_server.running:
                    time.sleep(0.1)
                    self.assertLess(time.time(), deadline, "RedisWalletNotifyHandler never become ready")

                client = redis.StrictRedis(host="localhost")
                client.publish("bitcoind_walletnotify_pubsub", "faketransactionid")

                deadline = time.time() + 15
                while self.walletnotify_server.message_count == 0:
                    time.sleep(0.1)
                    self.assertTrue(self.walletnotify_server.running)
                    self.assertTrue(self.walletnotify_server.is_alive())
                    self.assertLess(time.time(), deadline, "RedisWalletNotifyHandler did not get any messages")

                mock_method.assert_called_with("faketransactionid")

        finally:

            self.walletnotify_server.stop()
