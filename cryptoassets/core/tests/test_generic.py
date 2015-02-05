import os
import unittest
from decimal import Decimal

from ..app import CryptoAssetsApp
from ..configure import Configurator
from ..models import BadAddress

from . import testwarnings
from . import testlogging


class GenericWalletTestCase(unittest.TestCase):
    """Generic test cases which should be the same across all coins and do not rely on any backend functionality."""

    def setUp(self):
        """
        """

        testwarnings.begone()
        testlogging.setup()

        self.app = CryptoAssetsApp()
        self.configurator = Configurator(self.app)

        echo = "VERBOSE_TEST" in os.environ
        overrides = {"database": {"echo": echo}}

        test_config = os.path.join(os.path.dirname(__file__), "null.config.yaml")
        self.assertTrue(os.path.exists(test_config), "Did not found {}".format(test_config))
        self.configurator.load_yaml_file(test_config, overrides)

        self.app.setup_session()
        self.app.create_tables()

    def test_create_wallet_by_name(self):
        """Test creating and retrieving wallet by name."""

        with self.app.conflict_resolver.transaction() as session:
            wallet_class = self.app.coins.get("btc").wallet_model
            wallet = wallet_class.get_or_create_by_name("foobar", session)
            session.flush()
            self.assertEqual(wallet.id, 1)

        with self.app.conflict_resolver.transaction() as session:
            wallet_class = self.app.coins.get("btc").wallet_model
            wallet = wallet_class.get_or_create_by_name("foobar", session)
            session.flush()
            self.assertEqual(wallet.id, 1)

    def test_send_to_bad_address(self):
        """Try to send to bad address.
        """

        with self.app.conflict_resolver.transaction() as session:
            wallet_class = self.app.coins.get("btc").wallet_model

            wallet = wallet_class.get_or_create_by_name("foobar", session)
            session.flush()
            self.assertEqual(wallet.id, 1)

            account1 = wallet.get_or_create_account_by_name("account1")
            session.flush()

            with self.assertRaises(BadAddress):
                wallet.send_external(account1, "foobar", 0.1, "foobar")

    def test_automatic_address_label(self):
        """Check that we can generate address labels correctly."""

        with self.app.conflict_resolver.transaction() as session:
            wallet_class = self.app.coins.get("btc").wallet_model

            wallet = wallet_class.get_or_create_by_name("foobar", session)
            session.flush()
            self.assertEqual(wallet.id, 1)

            account1 = wallet.get_or_create_account_by_name("account1")
            session.flush()

            wallet.create_receiving_address(account1, automatic_label=True)
            session.flush()

            address2 = wallet.create_receiving_address(account1, automatic_label=True)
            self.assertTrue("#2" in address2.label)

    def test_get_deposits(self):
        """Create internal, incoming transactions and broadcasted transactions and see we can tell deposits apart."""

        with self.app.conflict_resolver.transaction() as session:
            wallet_class = self.app.coins.get("btc").wallet_model
            Transaction = self.app.coins.get("btc").transaction_model
            NetworkTransaction = self.app.coins.get("btc").network_transaction_model

            wallet = wallet_class.get_or_create_by_name("foobar", session)
            session.flush()
            self.assertEqual(wallet.id, 1)

            account1 = wallet.get_or_create_account_by_name("account1")
            account2 = wallet.get_or_create_account_by_name("account2")
            session.flush()
            receiving_addr = wallet.create_receiving_address(account1, "test incoming")

            account2.balance = Decimal(100)
            wallet.send_internal(account2, account1, Decimal(10), receiving_addr.address)
            session.flush()

            # Now let's see we get one deposit
            desposits = wallet.get_deposit_transactions()
            # self.assertEqual(desposits.count(), 0)
            self.assertEqual(session.query(Transaction).count(), 1)

            # Create deposit
            ntx, created = NetworkTransaction.get_or_create_deposit(session, "foobar")
            session.flush()
            account, transaction = wallet.deposit(ntx, receiving_addr.address, Decimal(20), extra=dict(confirmations=999))
            session.flush()
            assert account
            assert transaction.id
            assert transaction.network_transaction.id
            assert transaction.txid

            self.assertEqual(session.query(Transaction).count(), 2)

            # Now let's see we get one deposit
            desposits = wallet.get_deposit_transactions()
            self.assertEqual(desposits.count(), 1)

            # Create outgoing transaction + broadcast
            broadcast = NetworkTransaction()
            broadcast.txid = "foobar2"
            broadcast.transaction_type = "broadcast"
            broadcast.state = "pending"
            session.add(broadcast)
            session.flush()

            transaction = Transaction()
            transaction.network_transaction = broadcast
            transaction.sending_account = account2
            transaction.state = "pending"
            transaction.wallet = wallet
            out_addr = wallet.get_or_create_external_address("foobar2")
            session.flush()
            transaction.address = out_addr
            session.add(transaction)
            session.flush()

            # Broadcasts should not count as deposits
            desposits = wallet.get_deposit_transactions()
            self.assertEqual(desposits.count(), 1)

    def test_get_unconfirmed_balance(self):
        """Check balance of incoming transctions."""

        with self.app.conflict_resolver.transaction() as session:
            wallet_class = self.app.coins.get("btc").wallet_model
            NetworkTransaction = self.app.coins.get("btc").network_transaction_model

            wallet = wallet_class.get_or_create_by_name("foobar", session)
            session.flush()

            account1 = wallet.get_or_create_account_by_name("account1")
            account2 = wallet.get_or_create_account_by_name("account2")
            session.flush()

            self.assertEqual(account1.get_unconfirmed_balance(), Decimal(0))

            receiving_addr = wallet.create_receiving_address(account1, "test incoming")
            receiving_addr_2 = wallet.create_receiving_address(account2, "test incoming")
            session.flush()

            self.assertEqual(account1.get_unconfirmed_balance(), Decimal(0))

            account2.balance = Decimal(100)
            wallet.send_internal(account2, account1, Decimal(10), receiving_addr.address)
            session.flush()

            # Create deposit to account1
            ntx, created = NetworkTransaction.get_or_create_deposit(session, "foobar")
            session.flush()
            account, transaction = wallet.deposit(ntx, receiving_addr.address, Decimal(20), extra=dict(confirmations=1))
            session.flush()

            # Create deposit to account2
            ntx, created = NetworkTransaction.get_or_create_deposit(session, "foobar")
            session.flush()
            account, transaction = wallet.deposit(ntx, receiving_addr_2.address, Decimal(30), extra=dict(confirmations=1))
            session.flush()

            self.assertEqual(account1.get_unconfirmed_balance(), Decimal(20))
