import os
import unittest

from ..configure import ConfigurationError
from ..configure import Configurator
from ..app import CryptoAssetsApp
from ..coin.registry import Coin
from ..coin.bitcoin.models import BitcoinWallet
from ..backend.bitcoind import Bitcoind

from . import testwarnings


class ConfigureTestCase(unittest.TestCase):
    """Stress out configuration functionality and loading YAMLs."""

    def setUp(self):

        # ResourceWarning: unclosed <ssl.SSLSocket fd=9, family=AddressFamily.AF_INET, type=SocketType.SOCK_STREAM, proto=6, laddr=('192.168.1.4', 56386), raddr=('50.116.26.213', 443)>
        # http://stackoverflow.com/a/26620811/315168
        testwarnings.begone()

        self.app = CryptoAssetsApp()
        self.configurator = Configurator(self.app)

    def test_coins(self):
        """Test configuring coin backends.
        """

        coins = {
            "btc": {
                "backend": {
                    "class": "cryptoassets.core.backend.bitcoind.Bitcoind",
                    "url": "http://foo:bar@127.0.0.1:8332/",
                }
            }
        }

        coin_registry = self.configurator.setup_coins(coins)

        self.assertIsInstance(coin_registry.get("btc"), Coin)
        coin = coin_registry.get("btc")

        self.assertIsInstance(coin.backend, Bitcoind)
        self.assertEqual(coin.wallet_model, BitcoinWallet)

    def test_engine(self):
        """Test configuring the database engine."""
        config = {
            "url": 'sqlite://',
            "connect_args": {
                "check_same_thread": "false",
                "poolclass": "pool.StaticPool"
            }
        }
        engine = self.configurator.setup_engine(config)
        self.assertIsNotNone(engine)

    def test_load_yaml(self):
        """ Load a sample configuration file and see it's all dandy.
        """
        sample_file = os.path.join(os.path.dirname(__file__), "sample-config.yaml")
        self.assertTrue(os.path.exists(sample_file), "Did not found {}".format(sample_file))
        self.configurator.load_yaml_file(sample_file)

        self.assertIsNotNone(self.app.engine)

        coin = self.app.coins.get("btc")

        self.assertIsInstance(coin.backend, Bitcoind)
        self.assertEqual(coin.wallet_model, BitcoinWallet)

    def test_load_no_backend(self):
        """ Load broken configuration file where backends section is missing.
        """
        sample_file = os.path.join(os.path.dirname(__file__), "broken-config-no-backend.yaml")
        self.assertTrue(os.path.exists(sample_file), "Did not found {}".format(sample_file))

        def try_it():
            self.configurator.load_yaml_file(sample_file)

        self.assertRaises(ConfigurationError, try_it)
