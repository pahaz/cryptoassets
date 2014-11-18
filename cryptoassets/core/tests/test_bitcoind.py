"""Bitcoind raw JSON-RPC testing.

Test bitcoind API.
"""
import os
import time
import unittest

from sqlalchemy import create_engine

from ..models import DBSession
from ..models import Base
from ..backend import registry as backendregistry

from ..backend.bitcoind import Bitcoind
from ..backend import registry as backendregistry

from .. import configure
from .base import CoinTestCase

# https://github.com/onenameio/coinkit/blob/master/coinkit/keypair.py#L51

class BitcoindTestCase(CoinTestCase, unittest.TestCase):
    """Run bitcoind tests on TESTNET network.

    Import a pre-defined private key where we have some TESTNET balance available for the tests.

    We need to have locally set up bitcoind running in testnet and its transaction hook set up to call our script.
    """

    def top_up_balance(self, wallet, account):
        """ Add some test balance on the wallet. """

    def setup_test_fund_address(self, wallet, account):
        # Import some TESTNET coins
        label = "Test import {}".format(time.time())
        private_key, public_address = os.environ["BITCOIND_TESTNET_FUND_ADDRESS"].split(":")
        self.backend.import_private_key(label, private_key)
        wallet.add_address(account, "Test import {}".format(time.time()), public_address)
        wallet.scan_wallet()

    def setup_receiving(self, wallet):
        pass

    def teardown_receiving(self):
        pass

    def setup_coin(self):

        test_config = os.path.join(os.path.dirname(__file__), "bitcoind.config.yaml")
        self.assertTrue(os.path.exists(test_config), "Did not found {}".format(test_config))
        configure.load_yaml_file(test_config)

        self.backend = backendregistry.get("btc")

        from ..coin.bitcoin.models import BitcoinWallet
        from ..coin.bitcoin.models import BitcoinAddress
        from ..coin.bitcoin.models import BitcoinTransaction
        from ..coin.bitcoin.models import BitcoinAccount
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
