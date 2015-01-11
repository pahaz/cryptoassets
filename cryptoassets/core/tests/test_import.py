import os
import unittest

from ..app import CryptoAssetsApp
from ..configure import Configurator

from . import testwarnings
from ..tools import walletimport


class ImportBalanceTestCase(unittest.TestCase):
    """See that we can properly import balances on a wallet to our accounts."""

    def setUp(self):
        """
        """

        testwarnings.begone()

        self.app = CryptoAssetsApp()
        self.configurator = Configurator(self.app)

        test_config = os.path.join(os.path.dirname(__file__), "null.config.yaml")
        self.assertTrue(os.path.exists(test_config), "Did not found {}".format(test_config))
        self.configurator.load_yaml_file(test_config)

        self.app.setup_session()
        self.app.create_tables()

    def test_import_balance(self):
        """Test creating and retrieving wallet by name."""

        null_test_balance = 999999
        coin = self.app.coins.get("btc")
        Wallet = coin.wallet_model
        Transaction = coin.transaction_model
        backend = coin.backend

        with self.app.conflict_resolver.transaction() as session:

            w = Wallet()
            session.add(w)
            session.flush()

            self.assertTrue(walletimport.has_unaccounted_balance(backend, w))

            a = w.get_or_create_account_by_name("Imported balance")
            session.flush()

            walletimport.import_unaccounted_balance(coin.backend, w, a)
            session.flush()

            # Reload account
            a = w.get_or_create_account_by_name("Imported balance")
            self.assertEqual(a.balance, null_test_balance)
            txs = session.query(Transaction)
            self.assertEqual(txs.count(), 1)
            self.assertEqual(w.balance, null_test_balance)
            self.assertEqual(a.balance, null_test_balance)

        # Now we import again... because balances matches
        # nothing should happen
        with self.app.conflict_resolver.transaction() as session:

            w = session.query(Wallet).get(1)

            self.assertFalse(walletimport.has_unaccounted_balance(backend, w))

            a = w.get_or_create_account_by_name("Imported balance")
            walletimport.import_unaccounted_balance(coin.backend, w, a)
            session.flush()

            # Reload account
            a = w.get_or_create_account_by_name("Imported balance")
            self.assertEqual(a.balance, null_test_balance)
            txs = session.query(Transaction)
            self.assertEqual(txs.count(), 1)
            self.assertEqual(w.balance, null_test_balance)
            self.assertEqual(a.balance, null_test_balance)
