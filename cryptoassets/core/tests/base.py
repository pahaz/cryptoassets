import abc
import os
import transaction
import time
import logging
import sys
import warnings

from sqlalchemy.exc import IntegrityError
from sqlalchemy import create_engine
from sqlalchemy import pool
from pyramid import testing

from ..models import DBSession
from ..models import NotEnoughAccountBalance
from ..models import SameAccount

from . import testlogging

testlogging.setup()


class CoinTestCase:
    """Abstract base class for all cryptocurrency backend tests.

    Inherit form this test case, implement abstract method and run the test case.
    If all test passes, the backend is compatible with `cryptoassets.core`.
    """

    def setUp(self):

        # ResourceWarning: unclosed <ssl.SSLSocket fd=9, family=AddressFamily.AF_INET, type=SocketType.SOCK_STREAM, proto=6, laddr=('192.168.1.4', 56386), raddr=('50.116.26.213', 443)>
        # http://stackoverflow.com/a/26620811/315168
        warnings.filterwarnings("ignore", category=ResourceWarning)  # noqa

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

    def create_engine(self):
        """Create SQLAclhemy database engine for the tests."""

        # XXX: Not sure what would be the correct way to run tests,
        # so that we respect transaction consistency in external received transactions
        # which are usually done in external thread or process
        # pool = pool.SingletonThreadPool()
        # engine = create_engine('sqlite:///unittest.sqlite', echo=False, poolclass=pool.SingletonThreadPool)

        engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=pool.StaticPool)

        return engine

    @abc.abstractmethod
    def setup_receiving(self, wallet):
        """Necerssary setup to monitor incoming transactions for the backend."""

    @abc.abstractmethod
    def teardown_receiving(self):
        """Teardown incoming transaction monitoring."""

    @abc.abstractmethod
    def setup_coin(self):
        """Setup coin backend for this test case."""

    def wait_receiving_address_ready(self, wallet, address):
        """Wait that API service gets the address on the monitored list."""

    def setup_balance(self):
        """Create an a wallet and an account with balance. """

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

        self.setup_balance()

        with transaction.manager:
            account = DBSession.query(self.Account).get(1)
            # Assume we have at least 5 TESTNET bitcoins there
            self.assertIsNot(account.balance, 0, "Account balance was zero after refresh_account_balance()")
            self.assertGreater(account.balance, 5)

    def test_send_external(self):
        """ Send Bitcoins from external address """

        self.setup_balance()

        with transaction.manager:

            wallet = DBSession.query(self.Wallet).get(1)
            account = DBSession.query(self.Account).get(1)

            receiving_address = wallet.create_receiving_address(account, "Test address {}".format(time.time()))

            # Send Bitcoins through BlockChain
            tx = wallet.send_external(account, receiving_address.address, self.external_send_amount, "Test send {}".format(time.time()))

            # We should have created one transaction
            # which is not broadcasted yet
            self.assertGreater(DBSession.query(self.Transaction.id).count(), 0)
            self.assertEqual(tx.sending_account, account)
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

        self.setup_balance()

        with transaction.manager:
            account = DBSession.query(self.Account).get(1)
            wallet = DBSession.query(self.Wallet).get(1)

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

        This is especially tricky test case, as we are reusing some of the old
        test addresses for the sending the transaction and they may have
        extra outgoing and incoming transactions ready to hit from the previous tests.
        """

        try:

            self.Transaction.confirmation_count = self.external_transaction_confirmation_count

            self.setup_balance()
            wallet_id = 1

            with transaction.manager:

                # Reload objects from db for this transaction
                wallet = DBSession.query(self.Wallet).get(wallet_id)
                account = DBSession.query(self.Account).get(1)
                txs_before_send = wallet.get_external_received_transactions().count()

                # Create account for receiving the tx
                receiving_account = wallet.create_account("Test receiving account {}".format(time.time()))
                DBSession.flush()
                receiving_address = wallet.create_receiving_address(receiving_account, "Test receiving address {}".format(time.time()))

                # See that the created address was properly committed
                self.assertGreater(wallet.get_receiving_addresses().count(), 0)
                self.setup_receiving(wallet)

                self.wait_receiving_address_ready(wallet, receiving_address)

                tx = wallet.send(account, receiving_address.address, self.external_send_amount, "Test send", force_external=True)
                self.assertEqual(tx.state, "pending")
                self.assertEqual(tx.label, "Test send")

                broadcasted_count = wallet.broadcast()
                self.assertEqual(tx.state, "broadcasted")
                self.assertEqual(broadcasted_count, 1)

                receiving_address_id = receiving_address.id

                # Wait until backend notifies us the transaction has been received
                logger.info("Monitoring address {} on wallet {}".format(receiving_address.address, wallet.id))

            deadline = time.time() + self.external_receiving_timeout
            succeeded = False

            while time.time() < deadline:
                time.sleep(0.5)

                # Don't hold db locked for an extended perior
                with transaction.manager:
                    wallet = DBSession.query(self.Wallet).get(wallet_id)
                    address = DBSession.query(wallet.Address).filter(self.Address.id == receiving_address_id)
                    self.assertEqual(address.count(), 1)
                    account = address.first().account
                    txs = wallet.get_external_received_transactions()

                    # print(account.balance, len(wallet.transactions), wallet.get_active_external_received_transcations().count())

                    # The transaction is confirmed and the account is credited
                    # and we have no longer pending incoming transaction
                    if account.balance > 0 and wallet.get_active_external_received_transcations().count() == 0 and len(wallet.transactions) >= 3:
                        succeeded = True
                        break

            self.assertTrue(succeeded, "Never got the external transaction status through database")

        finally:
            self.Transaction.confirmation_count = 3
            self.teardown_receiving()

        # Final checks
        with transaction.manager:
            account = DBSession.query(self.Account).filter(self.Account.wallet_id == wallet_id).first()
            wallet = DBSession.query(self.Wallet).get(wallet_id)
            self.assertGreater(account.balance, 0, "Timeouted receiving external transaction")

            # 1 broadcasted, 1 network fee, 1 external
            self.assertGreaterEqual(len(wallet.transactions), 3)

            # The transaction should be external
            txs = wallet.get_external_received_transactions()
            self.assertEqual(txs.count(), txs_before_send + 1)

            # The transaction should no longer be active
            txs = wallet.get_active_external_received_transcations()
            self.assertEqual(txs.count(), 0)

            self.assertGreater(account.balance, 0, "Timeouted receiving external transaction")
