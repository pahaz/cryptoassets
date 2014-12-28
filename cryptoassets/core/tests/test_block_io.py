import os
import unittest
import time
import logging
from decimal import Decimal

from mock import patch

from sqlalchemy.orm.session import Session


from ..models import _now
from ..models import DBSession

from .base import CoinTestCase


logger = logging.getLogger(__name__)


#: This is a known address in the testnet test wallet with some funds on it
BLOCK_IO_TESTNET_TEST_FUND_ADDRESS = "2MsgW3kCrRFtJuo9JNjkorWXaZSvLk4EWRr"


class BlockIoBTCTestCase(CoinTestCase, unittest.TestCase):
    """ Test that our BTC accounting works on top of block.io API. """

    def setup_receiving(self, wallet):

        # Print out exceptions in Pusher messaging
        from websocket._core import enableTrace

        logger = logging.getLogger()
        if logger.level < logging.WARN:
            enableTrace(True)

        self.incoming_transactions_runnable = self.backend.setup_incoming_transactions(self.app.conflict_resolver, self.app.notifiers)

        self.incoming_transactions_runnable.start()

    def teardown_receiving(self):

        incoming_transactions_runnable = getattr(self, "incoming_transactions_runnable", None)
        if incoming_transactions_runnable:
            incoming_transactions_runnable.stop()

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

        self.external_transaction_confirmation_count = 0

        # Withdrawal amounts must be at least 0.00002000 BTCTEST, and at most 50.00000000 BTCTEST.
        self.external_send_amount = Decimal(2100) / Decimal(10**8)
        self.network_fee = Decimal(1000) / Decimal(10**8)
        # Wait 10 minutes for 1 confimation from the BTC TESTNET
        self.external_receiving_timeout = 60 * 10

    def is_address_monitored(self, wallet, address):
        """ Check if we can get notifications from an incoming transactions for a certain address.

        :param wallet: Wallet object

        :param address: Address object
        """

        if len(self.incoming_transactions_runnable.wallets) == 0:
            return False

        return address.address in self.incoming_transactions_runnable.wallets[wallet.id]["addresses"]

    def wait_receiving_address_ready(self, wallet, receiving_address):

        # Let the Pusher to build the connection
        # Make sure SoChain started to monitor this address
        deadline = time.time() + 5
        while time.time() < deadline:
            if self.is_address_monitored(wallet, receiving_address):
                break

        self.assertTrue(self.is_address_monitored(wallet, receiving_address), "The receiving address didn't become monitored {}".format(receiving_address.address))

    def test_get_active_transactions(self):
        """ Query for the list of unconfirmed transactions.
        """

        # Spoof three transactions
        # - one internal
        # - one external, confirmed
        # - one external, unconfirmed
        #

        with self.app.conflict_resolver.transaction() as session:
            wallet = self.Wallet()
            session.add(wallet)
            session.flush()

            account = wallet.create_account("Test account")
            session.flush()

            address = wallet.create_receiving_address(account, "Test address {}".format(time.time()))
            session.flush()

            # internal
            t = wallet.Transaction()
            t.sending_account = account
            t.receiving_account = account
            t.amount = 1000
            t.wallet = wallet
            t.credited_at = _now()
            t.label = "tx1"
            session.add(t)

            # external, confirmed
            t = wallet.Transaction()
            t.sending_account = None
            t.receiving_account = account
            t.amount = 1000
            t.wallet = wallet
            t.credited_at = _now()
            t.label = "tx2"
            t.txid = "txid2"
            t.confirmations = 6
            t.address = address
            session.add(t)

            # external, unconfirmed
            t = wallet.Transaction()
            t.sending_account = None
            t.receiving_account = account
            t.amount = 1000
            t.wallet = wallet
            t.credited_at = None
            t.label = "tx3"
            t.txid = "txid3"
            t.confirmations = 1
            t.address = address
            session.add(t)

            session.flush()

            external_txs = wallet.get_external_received_transactions()
            self.assertEqual(external_txs.count(), 2)

            active_txs = wallet.get_active_external_received_transcations()
            self.assertEqual(active_txs.count(), 1)
            self.assertEqual(active_txs.first().txid, "txid3")
            self.assertEqual(active_txs.first().address.id, address.id)

    def test_send_receive_external_fast(self):
        """The same as test_send_receive_external(), but spoofs the external incoming transaction.

        With this test, we can test ``Wallet.receive()`` much faster.
        """

        try:

            with self.app.conflict_resolver.transaction() as session:
                wallet = self.Wallet()
                session.add(wallet)
                session.flush()

                account = wallet.create_account("Test sending account")
                session.flush()

                account = session.query(self.Account).filter(self.Account.wallet_id == wallet.id).first()
                assert account

                receiving_address = wallet.create_receiving_address(account, "Test address {}".format(time.time()))

                # We must commit here so that
                # the receiver thread sees the wallet
                wallet_id = wallet.id

            with self.app.conflict_resolver.transaction() as session:

                # Reload objects from db for this transaction
                wallet = session.query(self.Wallet).get(wallet_id)
                account = session.query(self.Account).filter(self.Account.wallet_id == wallet_id).first()
                self.assertEqual(wallet.get_receiving_addresses().count(), 1)
                receiving_address = wallet.get_receiving_addresses().first()

                # See that the created address was properly committed
                self.assertGreater(wallet.get_receiving_addresses().count(), 0)
                self.setup_receiving(wallet)

                # Let the Pusher to build the connection
                # Make sure SoChain started to monitor this address
                deadline = time.time() + 5
                while time.time() < deadline:
                    if self.is_address_monitored(wallet, receiving_address):
                        break

                self.assertTrue(self.is_address_monitored(wallet, receiving_address), "The receiving address didn't become monitored {}".format(receiving_address.address))

                # Sync wallet with the external balance
                self.setup_balance()

                tx = wallet.send(account, receiving_address.address, self.external_send_amount, "Test send", force_external=True)
                self.assertEqual(tx.state, "pending")
                self.assertEqual(tx.label, "Test send")

                broadcasted_count = wallet.broadcast()
                self.assertEqual(tx.state, "broadcasted")
                self.assertEqual(broadcasted_count, 1)

                receiving_address_id = receiving_address.id
                receiving_address_address = receiving_address.address

                # Wait until backend notifies us the transaction has been received
                logger.info("Monitoring address {} on wallet {}".format(receiving_address.address, wallet.id))

            spoofed_get_transactions = {
                "data": {
                    "txs": [
                        {
                            "txid": "spoofer",
                            "amounts_received": [
                                {
                                    "recipient": receiving_address_address,
                                    "amount": self.backend.to_external_amount(self.external_send_amount)
                                }
                            ],
                            "confirmations": 6
                        }
                    ]
                }
            }

            succeeded = False

            with patch.object(_BlockIo, 'api_call', return_value=spoofed_get_transactions):

                deadline = time.time() + self.external_receiving_timeout
                while time.time() < deadline:
                    time.sleep(0.5)

                    # Don't hold db locked for an extended perior
                    with self.app.conflict_resolver.transaction() as session:
                        wallet = DBSession.query(self.Wallet).get(wallet_id)
                        address = DBSession.query(wallet.Address).filter(self.Address.id == receiving_address_id)
                        self.assertEqual(address.count(), 1)
                        account = address.first().account
                        txs = wallet.get_external_received_transactions()

                        # The transaction is confirmed and the account is credited
                        # and we have no longer pending incoming transaction
                        if account.balance > 0 and wallet.get_active_external_received_transcations().count() == 0 and len(wallet.transactions) == 3:
                            succeeded = True
                            break

                self.assertTrue(succeeded, "Never got the external transaction status through database")

        finally:
            # Stop any pollers, etc. which might modify the transactions after we stopped spoofing
            self.teardown_receiving()

        # Final checks
        with self.app.conflict_resolver.transaction() as session:
            account = DBSession.query(self.Account).filter(self.Account.wallet_id == wallet_id).first()
            wallet = DBSession.query(self.Wallet).get(wallet_id)
            self.assertGreater(account.balance, 0, "Timeouted receiving external transaction")

            # 1 broadcasted, 1 network fee, 1 external
            self.assertEqual(len(wallet.transactions), 3)

            # The transaction should be external
            txs = wallet.get_external_received_transactions()
            self.assertEqual(txs.count(), 1)

            # The transaction should no longer be active
            txs = wallet.get_active_external_received_transcations()
            self.assertEqual(txs.count(), 0)

            self.assertGreater(account.balance, 0, "Timeouted receiving external transaction")


class BlockIoDogeTestCase(BlockIoBTCTestCase):

    def setup_coin(self):

        test_config = os.path.join(os.path.dirname(__file__), "blockio-dogecoin.config.yaml")
        self.assertTrue(os.path.exists(test_config), "Did not found {}".format(test_config))
        self.configurator.load_yaml_file(test_config)

        coin = self.app.coins.get("btc")
        self.backend = coin.backend

        self.Address = coin.address_model
        self.Wallet = coin.wallet_model
        self.Transaction = coin.transaction_model
        self.Account = coin.account_model

        # Withdrawal amounts must be at least 0.00002000 BTCTEST, and at most 50.00000000 BTCTEST.
        self.external_send_amount = 100
        self.network_fee = 1

        # for test_send_receive_external() the confirmation
        # count before we let the test pass
        self.external_transaction_confirmation_count = 2

        # Wait 3 minutes for 1 confimation from the BTC TESTNET
        self.external_receiving_timeout = 60 * 5

