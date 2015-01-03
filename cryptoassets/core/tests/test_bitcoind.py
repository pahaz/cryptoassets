"""Bitcoind raw JSON-RPC testing.

Test bitcoind API.
"""
import os
import time
import unittest
import subprocess
from decimal import Decimal
import logging

import pytest

from ..backend.bitcoind import TransactionUpdater
from ..tools import opentransactions

from ..backend.pipewalletnotify import PipedWalletNotifyHandler
from .base import CoinTestCase
from .base import has_local_bitcoind
from .base import is_slow_test_hostile

from . import danglingthreads

WALLETNOTIFY_PIPE = "/tmp/cryptoassets-unittest-walletnotify-pipe"


logger = logging.getLogger(__name__)


class BitcoindTestCase(CoinTestCase, unittest.TestCase):
    """Run bitcoind tests on TESTNET network.

    Import a pre-defined private key where we have some TESTNET balance available for the tests.

    We need to have locally set up bitcoind running in testnet and its transaction hook set up to call our script.
    """

    def refresh_account_balance(self, wallet, account):
        """ """
        transaction_updater = self.backend.create_transaction_updater(self.app.conflict_resolver, self.app.notifiers)

        # We should find at least one transaction topping up our testnet wallet
        found = transaction_updater.rescan_all()
        self.assertGreater(found, 0)

        # Because we have imported public address to database previously,
        # transaction_updater should have updated the balance on this address
        with self.app.conflict_resolver.transaction() as session:
            account = session.query(self.Account).get(account.id)
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

        self.transaction_updater = self.backend.create_transaction_updater(self.app.conflict_resolver, self.app.notifiers)

        self.walletnotify_pipe = PipedWalletNotifyHandler(self.transaction_updater, WALLETNOTIFY_PIPE)

        # If you need to set pdb breakpoints inside the transaction updater,
        # you need to first flip this around
        self.walletnotify_pipe.daemon = False

        self.walletnotify_pipe.start()

    def teardown_receiving(self):
        walletnotify_pipe = getattr(self, "walletnotify_pipe", None)
        if walletnotify_pipe:
            walletnotify_pipe.stop()

        danglingthreads.check_dangling_threads()

    def setup_coin(self):

        if "CI" in os.environ:
            # Assume tunneled bitcoind + HTTP walletnotify setup on port 30000
            test_config = os.path.join(os.path.dirname(__file__), "bitcoind.droneio.config.yaml")
        else:
            # Assume local bitcoind + piped walletnotify setup
            test_config = os.path.join(os.path.dirname(__file__), "bitcoind.config.yaml")

        self.assertTrue(os.path.exists(test_config), "Did not found {}".format(test_config))

        self.configurator.load_yaml_file(test_config)

        coin = self.app.coins.get("btc")
        self.backend = coin.backend

        self.Address = coin.address_model
        self.Wallet = coin.wallet_model
        self.Transaction = coin.transaction_model
        self.Account = coin.account_model

        self.external_transaction_confirmation_count = 1

        self.Transaction.confirmation_count = 1

        # Withdrawal amounts must be at least 0.00002000 BTCTEST, and at most 50.00000000 BTCTEST.
        self.external_send_amount = Decimal("21000") / Decimal(10**8)
        self.network_fee = Decimal("10000") / Decimal(10**8)
        # Wait 10 minutes for 1 confimation from the BTC TESTNET
        self.external_receiving_timeout = 80 * 10

    def test_incoming_transaction(self):
        """Check we get notification for the incoming transaction.

        We will

        # Create an testnet wallet with an account with old known address imported

        # We know one transcation which has gone to this address

        # We manually trigger walletnotify hook with the transaction id

        # WalletNotifier should fetch the transaction from bitcoind, consider it as received transaction

        # Account balance should be updated
        """

        # XXX: Move this to py.test skip condition after Python 3.4.2 release
        # https://bitbucket.org/hpk42/pytest/issue/528/test-causes-segfault
        if not has_local_bitcoind():
            return

        with self.app.conflict_resolver.transaction() as session:
            # Create a wallet
            wallet = self.Wallet()
            session.add(wallet)
            session.flush()

            # Spoof a fake address on the wallet
            account = wallet.create_account("Test account")
            session.flush()

            # Testnet transaction id we are spoofing
            # bfb0ef36cdf4c7ec5f7a33ed2b90f0267f2d91a4c419bcf755cc02d6c0176ebf-000
            # to
            # n23pUFwzyVUXd7t4nZLzkZoidbjNnbQLLr
            wallet.add_address(account, "Old known address with a transaction", "n23pUFwzyVUXd7t4nZLzkZoidbjNnbQLLr")

            coin = self.app.coins.get("btc")
            transaction_updater = TransactionUpdater(self.app.conflict_resolver, self.backend, coin, None)

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

        with self.app.conflict_resolver.transaction() as session:
            # Reload account from the database
            account = session.query(self.Account).get(account_id)
            self.assertEqual(account.balance, Decimal("1.2"))

        # Triggering the transaction update again should not change the balance
        subprocess.call("echo bfb0ef36cdf4c7ec5f7a33ed2b90f0267f2d91a4c419bcf755cc02d6c0176ebf >> {}".format(WALLETNOTIFY_PIPE), shell=True)

        deadline = time.time() + 3
        while transaction_updater.count == 1:
            time.sleep(0.1)
            self.assertLess(time.time(), deadline, "Transaction updater never kicked in")

        with self.app.conflict_resolver.transaction() as session:
            account = session.query(self.Account).get(account_id)
            self.assertEqual(account.balance, Decimal("1.2"))

        self.walletnotify_pipe.stop()

    @pytest.mark.skipif(is_slow_test_hostile(), reason="Running send + receive loop may take > 20 minutes")
    def test_open_transactions(self):
        """Test that we get confirmation count increase.

        This test will take > 15 minutes to run.

        We stress out ``tools.opentransactions`` functionality. See CoinBackend base class for comments.
        """

        self.Transaction.confirmation_count = 3

        self.setup_balance()

        with self.app.conflict_resolver.transaction() as session:

            # Reload objects from db for this transaction
            wallet = session.query(self.Wallet).get(1)
            account = session.query(self.Account).get(1)

            # Create account for receiving the tx
            receiving_account = wallet.create_account("Test receiving account {}".format(time.time()))
            session.flush()
            receiving_address = wallet.create_receiving_address(receiving_account, "Test receiving address {}".format(time.time()))

            self.setup_receiving(wallet)

        # Commit new receiveing address to the database

        with self.app.conflict_resolver.transaction() as session:
            self.wait_receiving_address_ready(wallet, receiving_address)

            # Make sure we don't have any balance beforehand
            receiving_account = session.query(self.Account).get(receiving_account.id)
            self.assertEqual(receiving_account.balance, 0, "Receiving account got some balance already before sending")

            logger.info("Sending from account %d to %s amount %f", account.id, receiving_address.address, self.external_send_amount)
            tx = wallet.send(account, receiving_address.address, self.external_send_amount, "Test send", force_external=True)
            session.flush()

            broadcasted_count = wallet.broadcast()

            self.assertEqual(broadcasted_count, 1)
            receiving_address_id = receiving_address.id

            # Wait until backend notifies us the transaction has been received
            logger.info("Monitoring receiving address {} on wallet {}".format(receiving_address.address, wallet.id))

        deadline = time.time() + self.external_receiving_timeout

        while time.time() < deadline:

            time.sleep(30)

            opentransactions.rescan(self.transaction_updater, 3)

            # Don't hold db locked for an extended perior
            with self.app.conflict_resolver.transaction() as session:
                wallet = session.query(self.Wallet).get(1)
                address = session.query(wallet.Address).get(receiving_address_id)
                account = address.account
                txs = wallet.get_external_received_transactions()

                logger.info("Checking out addr {} incoming txs {}".format(address.address, txs.count()))
                for tx in txs:
                    logger.debug(tx)

                # The transaction is confirmed and the account is credited
                # and we have no longer pending incoming transaction
                if txs.count() > 0:
                    assert txs.count() < 2
                    tx = txs[0]
                    if tx.confirmations >= 2:
                        # We got more than 1 confirmation, good, we are counting!
                        break

            self.assertLess(time.time(), deadline, "Never got confirmations update through")
