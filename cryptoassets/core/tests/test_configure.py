"""Test our configure file format.

"""
import os
import unittest
import warnings

from sqlalchemy import create_engine

from .. import configure
from ..backend import registry
from ..backend.blockio import BlockIo


class ConfigureTestCase(unittest.TestCase):
    """
    """

    def setUp(self):

        # ResourceWarning: unclosed <ssl.SSLSocket fd=9, family=AddressFamily.AF_INET, type=SocketType.SOCK_STREAM, proto=6, laddr=('192.168.1.4', 56386), raddr=('50.116.26.213', 443)>
        # http://stackoverflow.com/a/26620811/315168
        warnings.filterwarnings("ignore", category=ResourceWarning)  # noqa

    def test_backends(self):
        """Test configuring coin backends.
        """
        backends = {
            "btc": {
                "class": "cryptoassets.core.backend.blockio.BlockIo",
                "api_key": "923f-e3e9-a580-dfb2",
                "pin": "foobar123",
            }
        }

        configure.setup_backends(backends)

        self.assertIsInstance(registry.get("btc"), BlockIo)

    def test_models(self):
        """Test configuring coin backends.
        """
        engine = {
            "url": 'sqlite:///:memory:?check_same_thread=false',
            #"poolclass": "pool.StaticPool",
            "pool_size": 1,

        }
        configure.setup_engine(engine)

        models = [
            "cryptoassets.core.coin.bitcoin.models",
            "cryptoassets.core.coin.dogecoin.models"
        ]

        configure.setup_models(models)

    def test_engine(self):
        """Test configuring the database engine."""
        engine = {
            "url": 'sqlite://',
            "connect_args": {
                "check_same_thread": "false",
                "poolclass": "pool.StaticPool"
            }
        }
        configure.setup_engine(engine)

    def test_load_yaml(self):
        """ Load a sample configuration file and see it's all dandy.
        """
        sample_file = os.path.join(os.path.dirname(__file__), "sample-config.yaml")
        self.assertTrue(os.path.exists(sample_file), "Did not found {}".format(sample_file))
        configure.load_yaml_file(sample_file)
        configure.check()