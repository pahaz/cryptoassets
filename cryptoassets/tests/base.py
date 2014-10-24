import os
import transaction
import time
import logging
import sys
from rainbow_logging_handler import RainbowLoggingHandler

from sqlalchemy.exc import IntegrityError
from sqlalchemy import create_engine
from pyramid import testing

from ..models import DBSession
from ..models import NotEnoughAccountBalance
from ..models import SameAccount


formatter = logging.Formatter("[%(asctime)s] %(name)s %(funcName)s():%(lineno)d\t%(message)s")  # same as default

# setup `RainbowLoggingHandler`
# and quiet some logs for the test output
handler = RainbowLoggingHandler(sys.stderr)
handler.setFormatter(formatter)
logger = logging.getLogger()
logger.addHandler(handler)
logger.debug("debug msg")


logger = logging.getLogger("requests.packages.urllib3.connectionpool")
logger.setLevel(logging.ERROR)

# SQL Alchemy transactions
logger = logging.getLogger("txn")
logger.setLevel(logging.ERROR)

logger = logging.getLogger(__name__)


class CoinTestCase:
    """ Base class for different tests. """

    def create_engine(self):

        # Nuke previous test run
        if os.path.exists("unittest.sqlite"):
            os.remove("unittest.sqlite")

        engine = create_engine('sqlite:///unittest.sqlite', echo=False)

        return engine

    def setUp(self):

        self.config = testing.setUp()

        self.Address = None
        self.Transaction = None
        self.Wallet = None
        self.Account = None

        # How many satoshis we use in send_external()
        self.external_send_amount = 100
        self.network_fee = 1000

        self.setup_coin()

        # Purge old test data
        with transaction.manager:
            DBSession.query(self.Address).delete()
            DBSession.query(self.Transaction).delete()
            DBSession.query(self.Wallet).delete()
            DBSession.query(self.Account).delete()

    def setup_coin(self):
        raise NotImplementedError()

    def setup_test_find_address(self, wallet, acount):
        raise NotImplementedError()

    def tearDown(self):
        DBSession.remove()
        testing.tearDown()

    def test_create_address(self):
        """ Creates a new wallet and fresh bitcoin address there. """

        with transaction.manager:
            wallet = self.Wallet()
            DBSession.add(wallet)
            DBSession.flush()
            account = wallet.create_account("Test account")
            DBSession.flush()
            address = wallet.create_receiving_address(account, "Test address {}".format(time.time()))

            # TODO: Check for valid bitcoin addresss
            self.assertGreater(len(address.address), 10)

    def test_get_receiving_addresses(self):
        """ Creates a new wallet and fresh bitcoin address there. """

        with transaction.manager:
            wallet = self.Wallet()
            DBSession.add(wallet)
            DBSession.flush()

            self.assertEqual(wallet.get_receiving_addresses().count(), 0)

            account = wallet.create_account("Test account")
            DBSession.flush()
            wallet.create_receiving_address(account, "Test address {}".format(time.time()))

            self.assertEqual(wallet.get_receiving_addresses().count(), 1)

            # The second wallet should not affect the addresses on the first one
            wallet2 = self.Wallet()
            DBSession.add(wallet2)
            DBSession.flush()

            self.assertEqual(wallet2.get_receiving_addresses().count(), 0)

            account = wallet2.create_account("Test account")
            DBSession.flush()
            wallet2.create_receiving_address(account, "Test address {}".format(time.time()))

            self.assertEqual(wallet.get_accounts().count(), 1)
            self.assertEqual(wallet.get_receiving_addresses().count(), 1)
            self.assertEqual(wallet2.get_receiving_addresses().count(), 1)

            # Test 2 accounts in one wallet

            account2 = wallet2.create_account("Test account 2")
            DBSession.flush()
            wallet2.create_receiving_address(account2, "Test address {}".format(time.time()))

            self.assertEqual(wallet.get_receiving_addresses().count(), 1)
            self.assertEqual(wallet2.get_receiving_addresses().count(), 2)

    def test_create_account(self):
        """ Creates a new wallet and fresh bitcoin address there. """

        with transaction.manager:
            wallet = self.Wallet()
            DBSession.add(wallet)

            # Must flush before we refer to wallet pk
            DBSession.flush()

            account = wallet.create_account("Test account")
            self.assertEqual(account.balance, 0)

    def test_send_internal(self):
        """ Creates a new wallet and fresh bitcoin address there. """

        with transaction.manager:
            wallet = self.Wallet()
            DBSession.add(wallet)
            DBSession.flush()

            sending_account = wallet.create_account("Test account")
            receiving_account = wallet.create_account("Test account 2")
            DBSession.flush()
            sending_account.balance = 100

            wallet.send_internal(sending_account, receiving_account, 100, "Test transaction")
            self.assertEqual(receiving_account.balance, 100)
            self.assertEqual(sending_account.balance, 0)

            # We should have created one transaction
            self.assertEqual(DBSession.query(self.Transaction.id).count(), 1)
            tx = DBSession.query(self.Transaction).first()
            self.assertEqual(tx.sending_account, sending_account)
            self.assertEqual(tx.receiving_account, receiving_account)

    def test_send_internal_low_balance(self):
        """ Does internal transaction where balance requirement is not met. """

        with transaction.manager:
            wallet = self.Wallet()
            DBSession.add(wallet)
            DBSession.flush()
            sending_account = wallet.create_account("Test account")
            receiving_account = wallet.create_account("Test account 2")
            sending_account.balance = 100
            DBSession.flush()
            assert sending_account.id

            def test():
                wallet.send_internal(sending_account, receiving_account, 110, "Test transaction")

            self.assertRaises(NotEnoughAccountBalance, test)

    def test_send_internal_same_account(self):
        """ Does internal transaction where balance requirement is not met. """

        with transaction.manager:
            wallet = self.Wallet()
            DBSession.add(wallet)
            DBSession.flush()
            sending_account = wallet.create_account("Test account")
            sending_account.balance = 100
            DBSession.flush()
            assert sending_account.id

            def test():
                wallet.send_internal(sending_account, sending_account, 10, "Test transaction")

            self.assertRaises(SameAccount, test)

    def test_cannot_import_existing_address(self):
        """ Do not allow importing an address which already exists. """

        def test():

            with transaction.manager:
                wallet = self.Wallet()
                DBSession.add(wallet)

                account = wallet.create_account("Test account")
                DBSession.flush()
                address = wallet.create_receiving_address(account, "Test address {}".format(time.time()))
                self.assertEqual(DBSession.query(self.Address.id).count(), 1)

                wallet.add_address(account, "Test import {}".format(time.time()), address.address)

                # Should not be reached
                self.assertEqual(DBSession.query(self.Address.id).count(), 1)

        self.assertRaises(IntegrityError, test)

    def test_refresh_account_balance(self):
        """ Read the external balance to an account. """
        with transaction.manager:
            wallet = self.Wallet()
            DBSession.add(wallet)
            DBSession.flush()
            account = wallet.create_account("Test account")
            DBSession.flush()
            self.setup_test_fund_address(wallet, account)
            wallet.refresh_account_balance(account)

            # Assume we have at least 5 TESTNET bitcoins there
            self.assertIsNot(account.balance, 0, "Account balance was zero after refresh_account_balance()")
            self.assertGreater(account.balance, 5)

    def test_send_external(self):
        """ Send Bitcoins from external address """
        with transaction.manager:
            wallet = self.Wallet()
            DBSession.add(wallet)
            DBSession.flush()
            account = wallet.create_account("Test account")
            DBSession.flush()
            # Sync wallet with the external balance
            self.setup_test_fund_address(wallet, account)
            wallet.refresh_account_balance(account)

            receiving_address = wallet.create_receiving_address(account, "Test address {}".format(time.time()))

            # Send Bitcoins through BlockChain
            wallet.send_external(account, receiving_address.address, self.external_send_amount, "Test send {}".format(time.time()))

            # We should have created one transaction
            # which is not broadcasted yet
            self.assertEqual(DBSession.query(self.Transaction.id).count(), 1)
            tx = DBSession.query(self.Transaction).first()
            self.assertEqual(tx.sending_account, account.id)
            self.assertEqual(tx.receiving_account, None)
            self.assertEqual(tx.state, "pending")
            self.assertEqual(tx.txid, None)
            self.assertIsNone(tx.processed_at)
            wallet.broadcast()

            self.assertEqual(tx.state, "broadcasted")
            self.assertIsNotNone(tx.txid)
            self.assertIsNotNone(tx.processed_at)

    def test_charge_network_fee(self):
        """ Do an external transaction and see we account network fees correctly. """

        with transaction.manager:
            wallet = self.Wallet()
            DBSession.add(wallet)
            DBSession.flush()
            account = wallet.create_account("Test account")
            DBSession.flush()

            # Sync wallet with the external balance
            self.setup_test_fund_address(wallet, account)
            wallet.refresh_account_balance(account)

            receiving_address = wallet.create_receiving_address(account, "Test address {}".format(time.time()))
            DBSession.flush()

            # Send Bitcoins through BlockChain
            wallet.send_external(account, receiving_address.address, self.external_send_amount, "Test send {}".format(time.time()))
            DBSession.flush()

            wallet.broadcast()
            DBSession.flush()

            # Our fee account goes below zero, because network fees
            # are subtracted from there
            fee_account = wallet.get_or_create_network_fee_account()
            self.assertLess(fee_account.balance, 0)

            fee_txs = DBSession.query(self.Transaction).filter(self.Transaction.state == "network_fee")
            self.assertEqual(fee_txs.count(), 1)
            self.assertEqual(fee_txs.first().amount, self.network_fee)

    def test_broadcast_no_transactions(self):
        """ Broadcast must not fail even we don't have any transactions. """

        with transaction.manager:
            wallet = self.Wallet()
            DBSession.add(wallet)
            wallet.broadcast()

    def test_receive_external_spoofed(self):
        """ Test receiving external transaction.

        Don't actually receive anything, spoof the incoming transaction.
        """

        with transaction.manager:
            wallet = self.Wallet()
            DBSession.add(wallet)
            DBSession.flush()

            account = wallet.create_account("Test account")
            DBSession.flush()
            receiving_address = wallet.create_receiving_address(account, "Test address {}".format(time.time()))
            txid = "fakefakefakefake"
            wallet.receive(txid, receiving_address.address, 1000, dict(confirmations=0))

            # First we should just register the transaction
            txs = DBSession.query(self.Transaction).filter(self.Transaction.state == "incoming")
            self.assertEqual(txs.count(), 1)
            self.assertEqual(txs.first().amount, 1000)
            self.assertFalse(txs.first().can_be_confirmed())
            self.assertEqual(account.balance, 0)
            self.assertEqual(wallet.balance, 0)
            self.assertIsNone(txs.first().processed_at)

            # Exceed the confirmation threshold
            wallet.receive(txid, receiving_address.address, 1000, dict(confirmations=6))
            self.assertTrue(txs.first().can_be_confirmed())
            self.assertEqual(account.balance, 1000)
            self.assertEqual(wallet.balance, 1000)
            self.assertIsNone(txs.first().processed_at)

            # Mark the transaction as processed the transaction
            wallet.mark_transaction_processed(txs.first().id)

            txs = DBSession.query(self.Transaction).filter(self.Transaction.state == "processed")
            self.assertEqual(txs.count(), 1)
            self.assertIsNotNone(txs.first().processed_at)

    def test_send_receive_external(self):
        """ Test sending and receiving external transaction within the backend wallet.

        """

        self.receiving_timeout = 600

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

                # Wait until backend notifies us the transaction has been received
                logger.info("Monitoring address {} on wallet {}".format(receiving_address.address, wallet.id))

            deadline = time.time() + self.receiving_timeout
            while time.time() < deadline:
                time.sleep(0.5)
                continue

                # Don't hold db locked for an extended perior
                with transaction.manager:
                    wallet = DBSession.query(self.Wallet).get(wallet_id)
                    account = DBSession.query(wallet.Address).filter(self.Address.id == receiving_address_id).first()
                    if account.balance > 0:
                        break

            self.assertGreater(account.balance, 0, "Timeouted receiving external transaction")

            # Now we should see two transactions for the wallet
            # One we used to do external send
            # One we used to do external receive

        finally:
            self.teardown_receiving()
