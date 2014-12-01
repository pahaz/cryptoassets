import os
import unittest
import transaction

from ..app import CryptoAssetsApp
from ..configure import Configurator
from cryptoassets.core.models import DBSession



class GenericWalletTestCase(unittest.TestCase):
    """Generic test cases which should be the same across all coins and do not rely on any backend functionality."""

    def setUp(self):
        """
        """

        self.app = CryptoAssetsApp()
        self.configurator = Configurator(self.app)

        test_config = os.path.join(os.path.dirname(__file__), "null.config.yaml")
        self.assertTrue(os.path.exists(test_config), "Did not found {}".format(test_config))
        self.configurator.load_yaml_file(test_config)

        self.app.setup_session()
        self.app.create_tables()

    def test_create_wallet_by_name(self):
        """Test creating and retrieving wallet by name."""

        with transaction.manager:
            wallet_class = self.app.coins.get("btc").wallet_model
            wallet = wallet_class.get_or_create_by_name("foobar", DBSession)
            DBSession.flush()
            self.assertEqual(wallet.id, 1)

        with transaction.manager:
            wallet_class = self.app.coins.get("btc").wallet_model
            wallet = wallet_class.get_or_create_by_name("foobar", DBSession)
            DBSession.flush()
            self.assertEqual(wallet.id, 1)
