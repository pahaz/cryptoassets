import os
import unittest
import time
import logging

from mock import patch
import transaction

from ..models import DBSession
from ..models import Base
from ..models import _now
from ..backend import registry as backendregistry

from ..backend.blockio import BlockIo
from ..backend.blockio import _BlockIo
from ..backend.blockio import SochainMonitor
from ..backend.blockio import _convert_to_satoshi
from ..backend.blockio import _convert_to_decimal
from ..lock.simple import create_thread_lock


from .base import CoinTestCase
from .base import logger


class BlockIoBTCTestCase(CoinTestCase, unittest.TestCase):
    """ Test that our BTC accounting works on top of block.io API. """

    def setup_receiving(self, wallet):

        # Print out exceptions in Pusher messaging
        from ..backend.blockio import logger
        from websocket._core import enableTrace
        if logger.level < logging.WARN:
            enableTrace(True)

        self.backend.monitor = SochainMonitor(self.backend, [wallet], os.environ["PUSHER_API_KEY"], "btctest")

    def teardown_receiving(self):
        if self.backend.monitor:
            self.backend.monitor.close()

    def setup_coin(self):

        self.backend = BlockIo("btc", os.environ["BLOCK_IO_API_KEY"], os.environ["BLOCK_IO_PIN"], create_thread_lock)
        backendregistry.register("btc", self.backend)
        self.monitor = None

        # We cannot use :memory db as,
        # SQLite does not support multithread access for it
        # http://stackoverflow.com/a/15681692/315168

        engine = self.create_engine()

        from ..coin.bitcoin.models import BitcoinWallet
        from ..coin.bitcoin.models import BitcoinAddress
        from ..coin.bitcoin.models import BitcoinTransaction
        from ..coin.bitcoin.models import BitcoinAccount
        DBSession.configure(bind=engine)
        Base.metadata.create_all(engine)

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

    def setup_test_fund_address(self, wallet, account):
        # Import some TESTNET coins
        wallet.add_address(account, "Test import {}".format(time.time()), os.environ["BLOCK_IO_TESTNET_TEST_FUND_ADDRESS"])

    def is_address_monitored(self, wallet, address):
        """ Check if we can get notifications from an incoming transactions for a certain address.

        :param wallet: Wallet object

        :param address: Address object
        """
        if len(wallet.backend.monitor.wallets) == 0:
            return False

        return address.address in wallet.backend.monitor.wallets[wallet.id]["addresses"]

    def test_convert(self):
        """ Test amount conversions. """
        v = _convert_to_satoshi("1")
        v2 = _convert_to_decimal(v)
        self.assertEqual(float(v2), 1.0)

    def test_store_all_the_satoshis(self):
        """ See that we can correctly store very big amount of satoshi on the account. """
        v = _convert_to_satoshi("21000000")

        with transaction.manager:
            wallet = self.Wallet()
            DBSession.add(wallet)
            DBSession.flush()

            account = wallet.create_account("Test account")
            account.balance = v

        with transaction.manager:
            account = DBSession.query(self.Account).first()
            self.assertEqual(account.balance, v)

    def test_get_active_transactions(self):
        """ Query for the list of unconfirmed transactions.
        """

        # Spoof three transactions
        # - one internal
        # - one external, confirmed
        # - one external, unconfirmed

        with transaction.manager:
            wallet = self.Wallet()
            DBSession.add(wallet)
            DBSession.flush()

            account = wallet.create_account("Test account")
            DBSession.flush()

            address = wallet.create_receiving_address(account, "Test address {}".format(time.time()))
            DBSession.flush()

            # internal
            t = wallet.Transaction()
            t.sending_account = account
            t.receiving_account = account
            t.amount = 1000
            t.wallet = wallet
            t.credited_at = _now()
            t.label = "tx1"
            DBSession.add(t)

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
            DBSession.add(t)

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
            DBSession.add(t)

            DBSession.flush()

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

            with transaction.manager:
                wallet = self.Wallet()
                DBSession.add(wallet)
                DBSession.flush()

                account = wallet.create_account("Test sending account")
                DBSession.flush()

                account = DBSession.query(self.Account).filter(self.Account.wallet_id == wallet.id).first()
                assert account

                receiving_address = wallet.create_receiving_address(account, "Test address {}".format(time.time()))

                # We must commit here so that
                # the receiver thread sees the wallet
                wallet_id = wallet.id

            with transaction.manager:

                # Reload objects from db for this transaction
                wallet = DBSession.query(self.Wallet).get(wallet_id)
                account = DBSession.query(self.Account).filter(self.Account.wallet_id == wallet_id).first()
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
                self.setup_test_fund_address(wallet, account)
                wallet.refresh_account_balance(account)

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
                    with transaction.manager:
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
        with transaction.manager:
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

    def setup_test_fund_address(self, wallet, account):
        # Import some TESTNET coins
        wallet.add_address(account, "Test import {}".format(time.time()), os.environ["BLOCK_IO_DOGE_TESTNET_TEST_FUND_ADDRESS"])

    def setup_receiving(self, wallet):

        # Print out exceptions in Pusher messaging
        from ..backend.blockio import logger
        from websocket._core import enableTrace
        if logger.level < logging.WARN:
            enableTrace(True)

        self.backend.monitor = SochainMonitor(self.backend, [wallet], os.environ["PUSHER_API_KEY"], "dogetest")

    def setup_coin(self):

        self.backend = BlockIo("doge", os.environ["BLOCK_IO_API_KEY_DOGE"], os.environ["BLOCK_IO_PIN"], create_thread_lock)
        backendregistry.register("doge", self.backend)
        self.monitor = None

        engine = self.create_engine()
        from ..coin.dogecoin.models import DogeWallet
        from ..coin.dogecoin.models import DogeAddress
        from ..coin.dogecoin.models import DogeTransaction
        from ..coin.dogecoin.models import DogeAccount
        DBSession.configure(bind=engine)
        Base.metadata.create_all(engine)

        self.Address = DogeAddress
        self.Wallet = DogeWallet
        self.Transaction = DogeTransaction
        self.Account = DogeAccount

        # Withdrawal amounts must be at least 0.00002000 BTCTEST, and at most 50.00000000 BTCTEST.
        self.external_send_amount = 100
        self.network_fee = 1

        # for test_send_receive_external() the confirmation
        # count before we let the test pass
        self.external_transaction_confirmation_count = 2

        # Wait 3 minutes for 1 confimation from the BTC TESTNET
        self.external_receiving_timeout = 60 * 5
