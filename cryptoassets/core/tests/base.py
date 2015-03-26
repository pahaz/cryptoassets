import abc
import os
import time
import logging
from decimal import Decimal

import requests
import pytest

from sqlalchemy.exc import IntegrityError
from sqlalchemy import create_engine
from sqlalchemy import pool

from ..models import NotEnoughAccountBalance
from ..models import SameAccount

from ..app import CryptoAssetsApp
from ..app import Subsystem
from ..configure import Configurator
from ..tools import walletimport
from ..tools import broadcast
from ..tools import confirmationupdate
from ..tools import receivescan

from . import testlogging
from . import testwarnings
from ..utils import danglingthreads


logger = logging.getLogger(__name__)


_connected = None


def has_inet():
    """py.test condition for checking if we are online."""
    global _connected

    if _connected is None:
        try:
            requests.get("http://google.com")
            _connected = True
        except:
            _connected = False

    return _connected


def has_local_bitcoind():
    """Use this to disable some tests in CI enviroment where 15 minute deadline applies."""
    return "CI" not in os.environ


def is_slow_test_hostile():
    """Use this to disable some tests in CI enviroment where 15 minute deadline applies."""
    return "CI" in os.environ or "SKIP_SLOW_TEST" in os.environ


class CoinTestRoot:
    """Have only initialization methods for the tests."""

    def setUp(self):

        testwarnings.begone()
        testlogging.setup()

        self.app = CryptoAssetsApp([Subsystem.database, Subsystem.backend, Subsystem.event_handler_registry, Subsystem.incoming_transactions])
        self.configurator = Configurator(self.app)

        session = self.app.session

        self.Address = None
        self.Transaction = None
        self.Wallet = None
        self.Account = None
        self.NetworkTransaction = None

        # How many satoshis we use in send_external()
        self.external_send_amount = Decimal("0.0001")
        self.network_fee = Decimal("0.0001")

        # Looks like network fee on btctest varies so we need to have at least two different allowed fees
        self.allowed_network_fees = []

        self.setup_coin()

        self.app.setup_session()
        self.app.create_tables()

        # Purge old test data
        with self.app.conflict_resolver.transaction() as session:
            session.query(self.Address).delete()
            session.query(self.Transaction).delete()
            session.query(self.Wallet).delete()
            session.query(self.Account).delete()
            session.query(self.NetworkTransaction).delete()

    def create_engine(self):
        """Create SQLAclhemy database engine for the tests."""

        # XXX: Not sure what would be the correct way to run tests,
        # so that we respect transaction consistency in external received transactions
        # which are usually done in external thread or process
        # pool = pool.SingletonThreadPool()
        # engine = create_engine('sqlite:///unittest.sqlite', echo=False, poolclass=pool.SingletonThreadPool)

        engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=pool.StaticPool)

        return engine

    def wait_address(self, address):
        """block.io needs subscription refresh every time we create a new address.

        Because we do not have IPC mechanism to tell when block.io refresh is ready, we just wait few seconds for now. block.io poller should recheck the database for new addresses every second.
        """
        time.sleep(3)

    @abc.abstractmethod
    def setup_receiving(self, wallet):
        """Necerssary setup to monitor incoming transactions for the backend."""

    @abc.abstractmethod
    def teardown_receiving(self):
        """Teardown incoming transaction monitoring."""

    def tearDown(self):
        self.teardown_receiving()
        danglingthreads.check_dangling_threads()

    @abc.abstractmethod
    def setup_coin(self):
        """Setup coin backend for this test case."""

    def broadcast(self, wallet):
        broadcaster = broadcast.Broadcaster(wallet, self.app.conflict_resolver, self.backend)
        return broadcaster.do_broadcasts()

    def setup_balance(self):
        """Create an a wallet and an account with balance. """

        # These objects must be committed before setup_test_fund_address() is called
        with self.app.conflict_resolver.transaction() as session:
            wallet = self.Wallet()
            session.add(wallet)
            account = wallet.create_account("Test account")
            session.flush()
            walletimport.import_unaccounted_balance(self.backend, wallet, account)

        # Make sure we got balance after refresh
        with self.app.conflict_resolver.transaction() as session:
            account = session.query(self.Account).get(1)
            wallet = session.query(self.Wallet).get(1)
            self.assertGreater(account.balance, 0, "We need have some balance on the unit test wallet to proceed with the send test")


class CoinTestCase(CoinTestRoot):
    """Abstract base class for all cryptocurrency backend tests.

    This verifies that a cryptocurrency backend works against cryptoassets.core models API.

    Inherit from this test case, implement backend abstract methods and run the test case.
    If all test passes, the backend is compatible with *cryptoassets.core*.
    """

    def test_create_address(self):
        """ Creates a new wallet and fresh bitcoin address there. """

        with self.app.conflict_resolver.transaction() as session:
            wallet = self.Wallet()
            session.add(wallet)
            session.flush()
            account = wallet.create_account("Test account")
            session.flush()
            address = wallet.create_receiving_address(account, "Test address {}".format(time.time()))

            # TODO: Check for valid bitcoin addresss
            self.assertGreater(len(address.address), 10)

    def test_get_receiving_addresses(self):
        """ Creates a new wallet and fresh bitcoin address there. """

        with self.app.conflict_resolver.transaction() as session:
            wallet = self.Wallet()
            session.add(wallet)
            session.flush()

            self.assertEqual(wallet.get_receiving_addresses().count(), 0)

            account = wallet.create_account("Test account")
            session.flush()
            wallet.create_receiving_address(account, "Test address {}".format(time.time()))
            session.flush()
            self.assertEqual(wallet.get_receiving_addresses().count(), 1)

            # The second wallet should not affect the addresses on the first one
            wallet2 = self.Wallet()
            session.add(wallet2)
            session.flush()

            self.assertEqual(wallet2.get_receiving_addresses().count(), 0)

            account = wallet2.create_account("Test account")
            session.flush()
            wallet2.create_receiving_address(account, "Test address {}".format(time.time()))
            session.flush()

            self.assertEqual(wallet.get_accounts().count(), 1)
            self.assertEqual(wallet.get_receiving_addresses().count(), 1)
            self.assertEqual(wallet2.get_receiving_addresses().count(), 1)

            # Test 2 accounts in one wallet

            account2 = wallet2.create_account("Test account 2")
            session.flush()
            wallet2.create_receiving_address(account2, "Test address {}".format(time.time()))
            session.flush()

            self.assertEqual(wallet.get_receiving_addresses().count(), 1)
            self.assertEqual(wallet2.get_receiving_addresses().count(), 2)

    def test_create_account(self):
        """ Creates a new wallet and fresh bitcoin address there. """

        with self.app.conflict_resolver.transaction() as session:
            wallet = self.Wallet()
            session.add(wallet)

            # Must flush before we refer to wallet pk
            session.flush()

            account = wallet.create_account("Test account")
            self.assertEqual(account.balance, 0)

    def test_send_internal(self):
        """ Creates a new wallet and fresh bitcoin address there. """

        with self.app.conflict_resolver.transaction() as session:
            wallet = self.Wallet()
            session.add(wallet)
            session.flush()

            sending_account = wallet.create_account("Test account")
            receiving_account = wallet.create_account("Test account 2")
            session.flush()
            sending_account.balance = 100
            tx = wallet.send_internal(sending_account, receiving_account, Decimal(100), "Test transaction")
            self.assertEqual(receiving_account.balance, 100)
            self.assertEqual(sending_account.balance, 0)

        # ...
        # Write the transaction
        # ...

        with self.app.conflict_resolver.transaction() as session:
            # We should have created one transaction
            self.assertEqual(session.query(self.Transaction.id).count(), 1)
            tx = session.query(self.Transaction).first()
            self.assertEqual(tx.sending_account, sending_account)
            self.assertEqual(tx.receiving_account, receiving_account)

    def test_send_internal_low_balance(self):
        """ Does internal transaction where balance requirement is not met. """

        with self.app.conflict_resolver.transaction() as session:
            wallet = self.Wallet()
            session.add(wallet)
            session.flush()
            sending_account = wallet.create_account("Test account")
            receiving_account = wallet.create_account("Test account 2")
            sending_account.balance = 100
            session.flush()
            assert sending_account.id

            def test():
                wallet.send_internal(sending_account, receiving_account, Decimal(110), "Test transaction")

            self.assertRaises(NotEnoughAccountBalance, test)

    def test_send_internal_same_account(self):
        """ Does internal transaction where balance requirement is not met. """

        with self.app.conflict_resolver.transaction() as session:
            wallet = self.Wallet()
            session.add(wallet)
            session.flush()
            sending_account = wallet.create_account("Test account")
            sending_account.balance = 100
            session.flush()
            assert sending_account.id

            def test():
                wallet.send_internal(sending_account, sending_account, Decimal(10), "Test transaction")

            self.assertRaises(SameAccount, test)

    def test_cannot_import_existing_address(self):
        """ Do not allow importing an address which already exists. """

        def test():

            with self.app.conflict_resolver.transaction() as session:
                wallet = self.Wallet()
                session.add(wallet)

                account = wallet.create_account("Test account")
                session.flush()

                address = wallet.create_receiving_address(account, "Test address {}".format(time.time()))

            with self.app.conflict_resolver.transaction() as session:
                self.assertEqual(session.query(self.Address).count(), 1)

            with self.app.conflict_resolver.transaction() as session:

                wallet.add_address(account, "Test import {}".format(time.time()), address.address)
                # Should not be reached
                self.assertEqual(session.query(self.Address.id).count(), 1)

        self.assertRaises(IntegrityError, test)

    def test_refresh_account_balance(self):
        """ Read the external balance to an account. """

        self.setup_balance()

        with self.app.conflict_resolver.transaction() as session:
            account = session.query(self.Account).get(1)
            # Assume we have at least 5 TESTNET bitcoins there
            self.assertIsNot(account.balance, 0, "Account balance was zero after refresh_account_balance()")
            self.assertGreater(account.balance, Decimal("0.001"))

    def test_send_external(self):
        """ Send Bitcoins from external address """

        self.setup_balance()

        with self.app.conflict_resolver.transaction() as session:

            wallet = session.query(self.Wallet).get(1)
            account = session.query(self.Account).get(1)

            receiving_address = wallet.create_receiving_address(account, "Test address {}".format(time.time()))

            # Send Bitcoins through BlockChain
            tx = wallet.send_external(account, receiving_address.address, self.external_send_amount, "Test send {}".format(time.time()))
            session.flush()

            # We should have created one transaction
            # which is not broadcasted yet
            self.assertGreater(session.query(self.Transaction.id).count(), 0)
            self.assertEqual(tx.sending_account, account)
            self.assertEqual(tx.receiving_account, None)
            self.assertEqual(tx.state, "pending")
            self.assertEqual(tx.txid, None)
            self.assertIsNone(tx.processed_at)
            self.broadcast(wallet)

            # Reread the tranansaction
            tx = session.query(self.Transaction).get(tx.id)

            self.assertEqual(tx.state, "broadcasted")
            self.assertIsNotNone(tx.txid)
            self.assertIsNotNone(tx.processed_at)

    @pytest.mark.skipif(is_slow_test_hostile(), reason="This may take up to 20 minutes")
    def test_update_broadcast_confirmation_count(self):
        """Do a broadcast and see we get updates for the confirmation count."""

        self.setup_balance()
        Transaction = self.Transaction

        with self.app.conflict_resolver.transaction() as session:

            wallet = session.query(self.Wallet).get(1)
            account = session.query(self.Account).get(1)

            # Random address on block.io testnet test wallet
            tx = wallet.send_external(account, "2N5Ji2nCnvjTXDxsv9dPuKocXicctSuNs4n", self.external_send_amount, "Test send {}".format(time.time()))
            session.flush()

            self.broadcast(wallet)

            # Reread the tranansaction
            tx = session.query(self.Transaction).get(tx.id)
            self.assertEqual(tx.state, "broadcasted")
            self.assertIsNotNone(tx.network_transaction)
            tx_id = tx.id

        transaction_updater = self.backend.create_transaction_updater(self.app.conflict_resolver, None)

        deadline = time.time() + 40 * 60
        while time.time() < deadline:

            confirmationupdate.update_confirmations(transaction_updater, 5)

            time.sleep(5.0)

            with self.app.conflict_resolver.transaction() as session:
                tx = session.query(Transaction).get(tx_id)

                logger.debug("Polling transaction updates for txid %s, confirmations %d", tx.txid, tx.confirmations)

                if tx.network_transaction.confirmations >= 1:
                    break

                self.assertLess(time.time(), deadline, "Did not receive updates for broadcast tx {}".format(tx.network_transaction.txid))

        self.assertGreaterEqual(transaction_updater.stats["network_transaction_updates"], 1)
        # We should have
        # 1 update for 0 confirmations
        # 1 update for 1 confirmations
        self.assertEqual(transaction_updater.stats["broadcast_updates"], 2)
        self.assertEqual(transaction_updater.stats["deposit_updates"], 0)

    def test_charge_network_fee(self):
        """Do an external transaction and see we account network fees correctly."""

        self.setup_balance()

        with self.app.conflict_resolver.transaction() as session:
            account = session.query(self.Account).get(1)
            wallet = session.query(self.Wallet).get(1)

            receiving_address = wallet.create_receiving_address(account, "Test address {}".format(time.time()))
            session.flush()

            # Send Bitcoins through BlockChain
            wallet.send_external(account, receiving_address.address, self.external_send_amount, "Test send {}".format(time.time()))
            session.flush()

            txcount, fees = self.broadcast(wallet)
            self.assertEqual(txcount, 1)
            self.assertGreater(fees, 0)

            # Our fee account goes below zero, because network fees
            # are subtracted from there
            fee_account = wallet.get_or_create_network_fee_account()
            self.assertLess(fee_account.balance, 0)

            fee_txs = session.query(self.Transaction).filter(self.Transaction.state == "network_fee")
            self.assertEqual(fee_txs.count(), 1)

            allowed_fees = self.allowed_network_fees + [self.network_fee]
            fee = fee_txs.first().amount

            self.assertTrue(fee in allowed_fees, "Got fee {}, allowed {}".format(fee, allowed_fees))

    def test_broadcast_no_transactions(self):
        """ Broadcast must not fail even we don't have any transactions. """

        with self.app.conflict_resolver.transaction() as session:
            wallet = self.Wallet()
            session.add(wallet)
            session.flush()
            broadcaster = broadcast.Broadcaster(wallet, self.app.conflict_resolver, self.backend)

        broadcaster.do_broadcasts()

    def test_receive_external_spoofed(self):
        """ Test receiving external transaction.

        Don't actually receive anything, spoof the incoming transaction.
        """

        test_amount = 1000
        NetworkTransaction = self.NetworkTransaction

        with self.app.conflict_resolver.transaction() as session:
            wallet = self.Wallet()
            session.add(wallet)

            ntx, created = NetworkTransaction.get_or_create_deposit(session, "foobar")
            session.flush()

            account = wallet.create_account("Test account")
            session.flush()
            receiving_address = wallet.create_receiving_address(account, "Test address {}".format(time.time()))
            session.flush()
            wallet.deposit(ntx, receiving_address.address, test_amount, dict(confirmations=0))

        # ...
        # write the transaction
        # ...

        with self.app.conflict_resolver.transaction() as session:
            # First we should just register the transaction as incoming
            txs = session.query(self.Transaction).filter(self.Transaction.state == "incoming")
            self.assertEqual(txs.count(), 1)
            self.assertEqual(txs.first().amount, test_amount)
            self.assertFalse(txs.first().can_be_confirmed())
            self.assertEqual(account.balance, 0)
            self.assertEqual(wallet.balance, 0)
            self.assertIsNone(txs.first().processed_at)

            ntx, created = NetworkTransaction.get_or_create_deposit(session, "foobar")
            ntx.confirmations = 999
            # Exceed the confirmation threshold
            wallet.deposit(ntx, receiving_address.address, test_amount, dict(confirmations=6))

            txs = session.query(self.Transaction).filter(self.Transaction.state == "incoming")
            self.assertTrue(txs.first().can_be_confirmed())
            self.assertEqual(account.balance, test_amount)
            self.assertEqual(wallet.balance, test_amount)
            self.assertEqual(receiving_address.balance, test_amount)
            self.assertIsNone(txs.first().processed_at)

            # Mark the transaction as processed the transaction
            wallet.mark_transaction_processed(txs.first().id)

            txs = session.query(self.Transaction).filter(self.Transaction.state == "processed")
            self.assertEqual(txs.count(), 1)
            self.assertIsNotNone(txs.first().processed_at)

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

    @pytest.mark.skipif(is_slow_test_hostile(), reason="This may take up to few minutes")
    def test_receive_scan(self):
        """Make sure we don't miss transactions even if helper service is down.

        We simulate a missed transaction (backend deposit updates are not running) and then manually trigger rescan to see rescan picks up the transaction.
        """

        Address = self.Address

        # First create incoming address
        with self.app.conflict_resolver.transaction() as session:
            wallet = self.Wallet()
            session.add(wallet)
            session.flush()

            account = wallet.create_account("Test account")
            session.flush()
            address = wallet.create_receiving_address(account, "Test address {}".format(time.time()))
            addr_str = address.address

        # Then perform send to this address using raw backend, so we shouldn't get notification the incoming deposit
        txid, fees = self.backend.send(recipients={addr_str: self.external_send_amount}, label="Test broadcast")

        # Now ask backend until we know the tx is broadcasted
        deadline = time.time() + 30
        while True:
            txdata = self.backend.get_transaction(txid)
            if txdata["confirmations"] >= 0:
                break
            self.assertLess(time.time(), deadline)

        missed = receivescan.scan(self.app.coins, self.app.conflict_resolver, None)
        self.assertEqual(missed, 1)

        # Check that address is now credited
        with self.app.conflict_resolver.transaction() as session:
            address = session.query(Address).filter(Address.address == addr_str).first()
            self.assertGreater(len(address.transactions), 0)

    @pytest.mark.skipif(is_slow_test_hostile(), reason="May take > 20 minutes")
    def test_confirmation_updates(self):
        """Test that we get confirmation count increase for an incoming transaction.

        We stress out ``tools.confirmationupdate`` functionality. See CoinBackend base class for comments.

        This test will take > 15 minutes to run.

        Bitcoin testnet block rate is SLOW and we need to wait at least 2 blocks.

        http://blockexplorer.com/testnet
        """

        self.Transaction.confirmation_count = 3

        self.setup_balance()

        transaction_updater = self.backend.create_transaction_updater(self.app.conflict_resolver, None)

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

            # Make sure we don't have any balance beforehand
            receiving_account = session.query(self.Account).get(receiving_account.id)
            self.assertEqual(receiving_account.balance, 0, "Receiving account got some balance already before sending")

            logger.info("Sending from account %d to %s amount %f", account.id, receiving_address.address, self.external_send_amount)
            tx = wallet.send(account, receiving_address.address, self.external_send_amount, "Test send", force_external=True)
            session.flush()

            broadcasted_count, tx_fees = self.broadcast(wallet)

            self.assertEqual(broadcasted_count, 1)
            receiving_address_id = receiving_address.id

            # Wait until backend notifies us the transaction has been received
            logger.info("Monitoring receiving address {} on wallet {}".format(receiving_address.address, wallet.id))

        # Testnet seem to take confirmations up to 60 minutes... le fuu the shitcoin
        # We wait 2 hours!
        deadline = time.time() + 45 * 60

        while time.time() < deadline:

            confirmationupdate.update_confirmations(transaction_updater, 3)

            time.sleep(30)

            # Don't hold db locked for an extended perior
            with self.app.conflict_resolver.transaction() as session:
                wallet = session.query(self.Wallet).get(1)
                address = session.query(self.Address).get(receiving_address_id)
                account = address.account

                txs = wallet.get_deposit_transactions()

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

                if time.time() > deadline:
                    # Print some debug output to diagnose
                    for tx in session.query(self.Transaction).all():
                        logger.error(tx)

                    for ntx in session.query(self.NetworkTransaction).all():
                        logger.error(ntx)

            self.assertLess(time.time(), deadline, "Never got confirmations update through")
