import os
import unittest
from decimal import Decimal

from ..app import CryptoAssetsApp
from ..configure import Configurator

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
        overrides = {"database":{"echo": echo}}

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

    def test_get_desposits(self):
        """Create internal and incoming transactions and see we can tell deposits apart."""

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
            ntx = NetworkTransaction.get_or_create_deposit(session, "foobar")
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



