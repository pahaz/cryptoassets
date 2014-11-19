"""Bitcoind raw JSON-RPC testing.

Test bitcoind API.
"""
import os
import time
import unittest
import threading
import subprocess

from unittest.mock import patch

from sqlalchemy import create_engine

from ..models import DBSession
from ..models import Base
from ..backend import registry as backendregistry

from ..backend.bitcoind import Bitcoind
from ..backend import registry as backendregistry

from .. import configure
from ..service.pipe import PipedWalletNotifyHandler
from .base import CoinTestCase

WALLETNOTIFY_PIPE = "/tmp/cryptoassets-unittest-walletnotify-pipe"


class WalletNotifyPipeThread(PipedWalletNotifyHandler, threading.Thread):
    """A thread which handles reading from walletnotify named pipe.
    """

    def __init__(self, coin, name):
        PipedWalletNotifyHandler.__init__(self, coin, name)
        threading.Thread.__init__(self)
        self.daemon = True


class BitcoindTestCase(CoinTestCase, unittest.TestCase):
    """Run bitcoind tests on TESTNET network.

    Import a pre-defined private key where we have some TESTNET balance available for the tests.

    We need to have locally set up bitcoind running in testnet and its transaction hook set up to call our script.
    """

    def top_up_balance(self, wallet, account):
        """ Add some test balance on the wallet. """

    def setup_test_fund_address(self, wallet, account):
        # Import some TESTNET coins
        label = "Test import {}".format(time.time())
        private_key, public_address = os.environ["BITCOIND_TESTNET_FUND_ADDRESS"].split(":")
        self.backend.import_private_key(label, private_key)
        wallet.add_address(account, "Test import {}".format(time.time()), public_address)
        wallet.scan_wallet()

    def setup_receiving(self, wallet):
        self.walletnotify_pipe = WalletNotifyPipeThread(self.Wallet.coin, WALLETNOTIFY_PIPE)
        self.walletnotify_pipe.start()

    def teardown_receiving(self):
        walletnotify_pipe = getattr(self, "walletnotify_pipe")
        if walletnotify_pipe:
            walletnotify_pipe.stop()

    def setup_coin(self):

        test_config = os.path.join(os.path.dirname(__file__), "bitcoind.config.yaml")
        self.assertTrue(os.path.exists(test_config), "Did not found {}".format(test_config))
        configure.load_yaml_file(test_config)

        self.backend = backendregistry.get("btc")

        from ..coin.bitcoin.models import BitcoinWallet
        from ..coin.bitcoin.models import BitcoinAddress
        from ..coin.bitcoin.models import BitcoinTransaction
        from ..coin.bitcoin.models import BitcoinAccount
        self.Address = BitcoinAddress
        self.Wallet = BitcoinWallet
        self.Transaction = BitcoinTransaction
        self.Account = BitcoinAccount

        self.external_transaction_confirmation_count = 0

        # Withdrawal amounts must be at least 0.00002000 BTCTEST, and at most 50.00000000 BTCTEST.
        self.external_send_amount = 2100
        self.network_fee = 1000
        # Wait 10 minutes for 1 confimation from the BTC TESTNET
        self.external_receiving_timeout = 60 * 10

    def test_piped_walletnotify(self):
        """Check that we receive notifications through the named pipe"""

        wallet = self.Wallet()

        with patch.object(PipedWalletNotifyHandler, 'handle_tx_update', return_value=None) as mock_method:
            self.setup_receiving(wallet)

            # Wait until walletnotifier has set up the pipe
            deadline = time.time() + 25
            while not self.walletnotify_pipe.ready:
                time.sleep(0.1)
                self.assertLess(time.time(), deadline, "PipedWalletNotifyHandler never become ready")

            self.assertTrue(self.walletnotify_pipe.is_alive())
            self.assertTrue(os.path.exists(WALLETNOTIFY_PIPE))

            subprocess.call("echo faketransactionid >> {}".format(WALLETNOTIFY_PIPE), shell=True)
            time.sleep(0.1)  # Let walletnotify thread to pick it up

            mock_method.assert_called_once_with("faketransactionid")

