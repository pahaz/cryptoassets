"""Bitcoind raw JSON-RPC testing.

Test bitcoind API.
"""
import os
import time
import unittest
import threading
import subprocess
import transaction

from unittest.mock import patch

from sqlalchemy import create_engine

from ..models import DBSession
from ..models import Base
from ..backend import registry as backendregistry

from ..backend.bitcoind import Bitcoind
from ..backend.bitcoind import TransactionUpdater
from ..backend import registry as backendregistry

from .. import configure
from ..backend.pipe import PipedWalletNotifyHandler
from ..backend.httpwalletnotify import HTTPWalletNotifyHandler
from ..backend.httpwalletnotify import WalletNotifyRequestHandler
from .base import CoinTestCase


WALLETNOTIFY_PIPE = "/tmp/cryptoassets-unittest-walletnotify-pipe"


class BitcoindTestCase(CoinTestCase, unittest.TestCase):
    """Run bitcoind tests on TESTNET network.

    Import a pre-defined private key where we have some TESTNET balance available for the tests.

    We need to have locally set up bitcoind running in testnet and its transaction hook set up to call our script.
    """

    def refresh_account_balance(self, wallet, account):
        """ """
        transaction_updater = TransactionUpdater(DBSession, self.backend, "btc")

        # We should find at least one transaction topping up our testnet wallet
        found = transaction_updater.rescan_all(transaction.manager)
        self.assertGreater(found, 0)

        # Because we have imported public address to database previously,
        # transaction_updater should have updated the balance on this address
        account = DBSession.query(self.Account).get(account.id)
        self.assertGreater(account.balance, 0)

    def setup_test_fund_address(self, wallet, account):
        # Import some TESTNET coins
        assert wallet.id
        assert account.id
        label = "Test import {}".format(time.time())
        private_key, public_address = os.environ["BITCOIND_TESTNET_FUND_ADDRESS"].split(":")
        self.backend.import_private_key(label, private_key)
        wallet.add_address(account, "Test import {}".format(time.time()), public_address)
        self.assertGreater(wallet.get_receiving_addresses().count(), 0)

    def setup_receiving(self, wallet):

        self.transaction_updater = TransactionUpdater(DBSession, self.backend, "btc")

        self.walletnotify_pipe = PipedWalletNotifyHandler(self.transaction_updater, WALLETNOTIFY_PIPE)

        # If you need to set pdb breakpoints inside the transaction updater,
        # you need to first flip this around
        self.walletnotify_pipe.daemon = False

        self.walletnotify_pipe.start()

    def teardown_receiving(self):
        walletnotify_pipe = getattr(self, "walletnotify_pipe", None)
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

        self.external_transaction_confirmation_count = 1

        self.Transaction.confirmation_count = 1

        # Withdrawal amounts must be at least 0.00002000 BTCTEST, and at most 50.00000000 BTCTEST.
        self.external_send_amount = 21000
        self.network_fee = 10000
        # Wait 10 minutes for 1 confimation from the BTC TESTNET
        self.external_receiving_timeout = 60 * 10

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

    def test_incoming_transaction(self):
        """Check we get notification for the incoming transaction.

        We will

        # Create an testnet wallet with an account with old known address imported

        # We know one transcation which has gone to this address

        # We manually trigger walletnotify hook with the transaction id

        # WalletNotifier should fetch the transaction from bitcoind, consider it as received transaction

        # Account balance should be updated
        """

        with transaction.manager:
            # Create a wallet
            wallet = self.Wallet()
            DBSession.add(wallet)
            DBSession.flush()

            # Spoof a fake address on the wallet
            account = wallet.create_account("Test account")
            DBSession.flush()

            # Testnet transaction id we are spoofing
            # bfb0ef36cdf4c7ec5f7a33ed2b90f0267f2d91a4c419bcf755cc02d6c0176ebf-000
            # to
            # n23pUFwzyVUXd7t4nZLzkZoidbjNnbQLLr
            wallet.add_address(account, "Old known address with a transaction", "n23pUFwzyVUXd7t4nZLzkZoidbjNnbQLLr")

            transaction_updater = TransactionUpdater(DBSession, self.backend, "btc")

            account_id = account.id

        self.walletnotify_pipe = PipedWalletNotifyHandler(transaction_updater, WALLETNOTIFY_PIPE)
        self.walletnotify_pipe.start()

        # Wait until walletnotifier has set up the named pipe
        deadline = time.time() + 3
        while not self.walletnotify_pipe.ready:
            time.sleep(0.1)
            self.assertLess(time.time(), deadline, "PipedWalletNotifyHandler never become ready")

        subprocess.call("echo bfb0ef36cdf4c7ec5f7a33ed2b90f0267f2d91a4c419bcf755cc02d6c0176ebf >> {}".format(WALLETNOTIFY_PIPE), shell=True)

        deadline = time.time() + 3
        while transaction_updater.count == 0:
            time.sleep(0.1)
            self.assertLess(time.time(), deadline, "Transaction updater never kicked in")

        # Check that transaction manager did not die with an exception
        # in other thread
        self.assertEqual(transaction_updater.count, 1)
        self.assertTrue(self.walletnotify_pipe.is_alive())

        with transaction.manager:
            # Reload account from the database
            account = DBSession.query(self.Account).get(account_id)
            self.assertEqual(account.balance, 120000000)

        # Triggering the transaction update again should not change the balance
        subprocess.call("echo bfb0ef36cdf4c7ec5f7a33ed2b90f0267f2d91a4c419bcf755cc02d6c0176ebf >> {}".format(WALLETNOTIFY_PIPE), shell=True)

        deadline = time.time() + 3
        while transaction_updater.count == 1:
            time.sleep(0.1)
            self.assertLess(time.time(), deadline, "Transaction updater never kicked in")

        with transaction.manager:
            account = DBSession.query(self.Account).get(account_id)
            self.assertEqual(account.balance, 120000000)

        self.walletnotify_pipe.stop()

    def test_scan_wallet(self):
        """Rescan all wallet transactions and rebuild account balances."""

        # These objects must be committed before setup_test_fund_address() is called
        with transaction.manager:
            wallet = self.Wallet()
            DBSession.add(wallet)
            DBSession.flush()
            account = wallet.create_account("Test account")

        # Import addresses we know having received balance
        with transaction.manager:
            account = DBSession.query(self.Account).get(1)
            wallet = DBSession.query(self.Wallet).get(1)
            self.setup_test_fund_address(wallet, account)
            self.assertGreater(wallet.get_receiving_addresses().count(), 0)

        # Refresh from API/bitcoind the balances of imported addresses
        with transaction.manager:
            account = DBSession.query(self.Account).get(1)
            wallet = DBSession.query(self.Wallet).get(1)
            self.assertGreater(wallet.get_receiving_addresses().count(), 0)
            self.refresh_account_balance(wallet, account)

        # Make sure we got balance after refresh
        with transaction.manager:
            account = DBSession.query(self.Account).get(1)
            wallet = DBSession.query(self.Wallet).get(1)
            self.assertGreater(wallet.get_receiving_addresses().count(), 0)
            self.assertGreater(account.balance, 0, "We need have some balance on the test account to proceed with the send test")

