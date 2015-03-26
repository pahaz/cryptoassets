import os
import unittest
import logging
import time

import pytest

from decimal import Decimal

from .base import CoinTestCase
from .base import CoinTestRoot
from. base import is_slow_test_hostile
from ..tools import confirmationupdate
from ..utils import danglingthreads
from ..utils.tunnel import NgrokTunnel

from ..backend.blockio import clean_blockio_test_wallet

logger = logging.getLogger(__name__)


class BlockIoBTCTestCase(CoinTestCase, unittest.TestCase):
    """ Test that our BTC accounting works on top of block.io API.

    Use websockets notification interface.
    """

    test_wallet_cleaned = False

    def setup_receiving(self, wallet):

        self.incoming_transactions_runnable = self.backend.setup_incoming_transactions(self.app.conflict_resolver, self.app.event_handler_registry)

        self.incoming_transactions_runnable.start()

        self.incoming_transactions_runnable.wait_until_ready()

    def teardown_receiving(self):

        incoming_transactions_runnable = getattr(self, "incoming_transactions_runnable", None)
        if incoming_transactions_runnable:
            incoming_transactions_runnable.stop()

        danglingthreads.check_dangling_threads()

    def clean_test_wallet(self):
        """Make sure the test wallet does't become unmanageable on block.io backend."""
        if not self.test_wallet_cleaned:
            clean_blockio_test_wallet(self.backend, balance_threshold=Decimal(5000) / Decimal(10**8))
            self.test_wallet_cleaned = True

    def setup_coin(self):

        test_config = os.path.join(os.path.dirname(__file__), "blockio-bitcoin.config.yaml")
        self.assertTrue(os.path.exists(test_config), "Did not found {}".format(test_config))
        self.configurator.load_yaml_file(test_config)

        coin = self.app.coins.get("btc")
        self.backend = coin.backend

        self.Address = coin.address_model
        self.Wallet = coin.wallet_model
        self.Transaction = coin.transaction_model
        self.Account = coin.account_model
        self.NetworkTransaction = coin.network_transaction_model

        self.external_transaction_confirmation_count = 1

        # Withdrawal amounts must be at least 0.00002000 BTCTEST, and at most 50.00000000 BTCTEST.
        self.external_send_amount = Decimal(2100) / Decimal(10**8)
        self.network_fee = Decimal(1000) / Decimal(10**8)

        # Wait 15 minutes for 1 confimation from the BTC TESTNET
        self.external_receiving_timeout = 60 * 20

        self.clean_test_wallet()


class BlockIoDogeTestCase(BlockIoBTCTestCase):
    """Test that our Dogecoin accounting works on top of block.io API."""

    def setup_coin(self):

        test_config = os.path.join(os.path.dirname(__file__), "blockio-dogecoin.config.yaml")
        self.assertTrue(os.path.exists(test_config), "Did not found {}".format(test_config))
        self.configurator.load_yaml_file(test_config)

        coin = self.app.coins.get("doge")
        self.backend = coin.backend

        self.Address = coin.address_model
        self.Wallet = coin.wallet_model
        self.Transaction = coin.transaction_model
        self.Account = coin.account_model
        self.NetworkTransaction = coin.network_transaction_model

        # Withdrawal amounts must be at least 0.00002000 BTCTEST, and at most 50.00000000 BTCTEST.
        self.external_send_amount = Decimal("2")
        self.network_fee = Decimal("1")

        # for test_send_receive_external() the confirmation
        # count before we let the test pass
        self.external_transaction_confirmation_count = 2

        # Wait 3 minutes for 1 confimation from the BTC TESTNET
        self.external_receiving_timeout = 60 * 10

        self.clean_test_wallet()


class BlockWebhookTestCase(CoinTestRoot, unittest.TestCase):
    """Test that we get webhook notifications coming through."""

    def setup_coin(self):

        test_config = os.path.join(os.path.dirname(__file__), "blockio-dogecoin.config.yaml")
        self.assertTrue(os.path.exists(test_config), "Did not found {}".format(test_config))
        self.configurator.load_yaml_file(test_config)

        coin = self.app.coins.get("doge")
        self.backend = coin.backend

        self.Address = coin.address_model
        self.Wallet = coin.wallet_model
        self.Transaction = coin.transaction_model
        self.Account = coin.account_model
        self.NetworkTransaction = coin.network_transaction_model

        # Withdrawal amounts must be at least 0.00002000 BTCTEST, and at most 50.00000000 BTCTEST.
        self.external_send_amount = Decimal("2")
        self.network_fee = Decimal("1")

        # for test_send_receive_external() the confirmation
        # count before we let the test pass
        self.external_transaction_confirmation_count = 2

        # Wait 3 minutes for 1 confimation from the BTC TESTNET
        self.external_receiving_timeout = 60 * 10

    def setup_receiving(self, wallet):

        self.ngrok = None

        self.backend.walletnotify_config["class"] = "cryptoassets.core.backend.blockiowebhook.BlockIoWebhookNotifyHandler"

        # We need ngrok tunnel for webhook notifications
        auth_token = os.environ["NGROK_AUTH_TOKEN"]
        self.ngrok = NgrokTunnel(21211, auth_token)

        # Pass dynamically generated tunnel URL to backend config
        tunnel_url = self.ngrok.start()
        self.backend.walletnotify_config["url"] = tunnel_url
        self.backend.walletnotify_config["port"] = 21211

        self.incoming_transactions_runnable = self.backend.setup_incoming_transactions(self.app.conflict_resolver, self.app.event_handler_registry)

        self.incoming_transactions_runnable.start()

    def teardown_receiving(self):

        incoming_transactions_runnable = getattr(self, "incoming_transactions_runnable", None)
        if incoming_transactions_runnable:
            incoming_transactions_runnable.stop()

        danglingthreads.check_dangling_threads()

        if self.ngrok:
            self.ngrok.stop()
            self.ngrok = None

    @pytest.mark.skipif(is_slow_test_hostile(), reason="Running send + receive loop may take > 20 minutes")
    def test_send_receive_external(self):
        """ Test sending and receiving external transaction within the backend wallet.

        This is especially tricky test case, as we are reusing some of the old
        test addresses for the sending the transaction and they may have
        extra outgoing and incoming transactions ready to hit from the previous tests.
        """

        try:

            self.Transaction.confirmation_count = self.external_transaction_confirmation_count

            self.setup_balance()
            wallet_id = 1

            with self.app.conflict_resolver.transaction() as session:

                # Reload objects from db for this transaction
                wallet = session.query(self.Wallet).get(wallet_id)
                account = session.query(self.Account).get(1)
                txs_before_send = wallet.get_deposit_transactions().count()

                # Create account for receiving the tx
                receiving_account = wallet.create_account("Test receiving account {}".format(time.time()))
                session.flush()
                receiving_address = wallet.create_receiving_address(receiving_account, "Test receiving address {}".format(time.time()))

                session.flush()
                # See that the created address was properly committed
                self.assertGreater(wallet.get_receiving_addresses().count(), 0)
                self.setup_receiving(wallet)

                # Because of block.io needs subscription refresh for new addresses, we sleep here before we can think of sending anything to justly created address
                self.wait_address(receiving_address)

            # Commit new receiveing address to the database

            with self.app.conflict_resolver.transaction() as session:

                # Make sure we don't have any balance beforehand
                receiving_account = session.query(self.Account).get(receiving_account.id)
                self.assertEqual(receiving_account.balance, 0, "Receiving account got some balance already before sending")

                logger.info("Sending from account %d to %s amount %f", account.id, receiving_address.address, self.external_send_amount)
                tx = wallet.send(account, receiving_address.address, self.external_send_amount, "Test send", force_external=True)
                session.flush()
                self.assertEqual(tx.state, "pending")
                self.assertEqual(tx.label, "Test send")

                broadcasted_count, tx_fees = self.broadcast(wallet)

                # Reread the changed transaction
                tx = session.query(self.Transaction).get(tx.id)
                self.assertEqual(tx.state, "broadcasted")
                self.assertEqual(broadcasted_count, 1)

                tx = session.query(self.Transaction).get(tx.id)
                logger.info("External transaction is %s", tx.txid)

                receiving_address_id = receiving_address.id
                tx_id = tx.id
                receiving_address_str = receiving_address.address

                # Wait until backend notifies us the transaction has been received
                logger.info("Monitoring receiving address {} on wallet {}".format(receiving_address.address, wallet.id))

            deadline = time.time() + self.external_receiving_timeout
            succeeded = False

            while time.time() < deadline:
                time.sleep(30.0)

                # Make sure confirmations are updated
                transaction_updater = self.backend.create_transaction_updater(self.app.conflict_resolver, None)
                confirmationupdate.update_confirmations(transaction_updater, 5)

                # Don't hold db locked for an extended perior
                with self.app.conflict_resolver.transaction() as session:
                    Address = self.Address
                    wallet = session.query(self.Wallet).get(wallet_id)
                    address = session.query(Address).filter(self.Address.id == receiving_address_id)
                    self.assertEqual(address.count(), 1)
                    account = address.first().account
                    txs = wallet.get_deposit_transactions()

                    print(account.name, account.balance, len(wallet.transactions), wallet.get_active_external_received_transcations().count())

                    # The transaction is confirmed and the account is credited
                    # and we have no longer pending incoming transaction
                    if account.balance > 0 and wallet.get_active_external_received_transcations().count() == 0 and len(wallet.transactions) >= 3:
                        succeeded = True
                        break

            # Check txid on
            # https://chain.so/testnet/btc
            self.assertTrue(succeeded, "Never got the external transaction status through database, backend:{} txid:{} receiving address:{} wait:{}s".format(self.backend, tx_id, receiving_address_str, self.external_receiving_timeout))

            # Just some debug output
            with self.app.conflict_resolver.transaction() as session:
                address = session.query(self.Address).filter(self.Address.id == receiving_address_id)
                account = address.first().account
                logger.info("Receiving account %d balance %f", account.id, account.balance)

                tx = session.query(self.Transaction).get(tx_id)
                logger.info("Broadcasted transaction %d txid %s confirmations %s", tx.id, tx.txid, tx.confirmations)

        finally:
            self.Transaction.confirmation_count = 3
            self.teardown_receiving()

        # Final checks
        with self.app.conflict_resolver.transaction() as session:
            account = session.query(self.Account).filter(self.Account.wallet_id == wallet_id).first()
            wallet = session.query(self.Wallet).get(wallet_id)
            self.assertGreater(account.balance, 0, "Timeouted receiving external transaction")

            # 1 broadcasted, 1 network fee, 1 external
            self.assertGreaterEqual(len(wallet.transactions), 3)

            # The transaction should be external
            txs = wallet.get_deposit_transactions()
            self.assertEqual(txs.count(), txs_before_send + 1)

            # The transaction should no longer be active
            txs = wallet.get_active_external_received_transcations()
            self.assertEqual(txs.count(), 0)

            self.assertGreater(account.balance, 0, "Timeouted receiving external transaction")


