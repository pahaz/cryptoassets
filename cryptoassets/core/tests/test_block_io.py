import os
import unittest
import logging

from decimal import Decimal

from .base import CoinTestCase
from ..utils import danglingthreads
from ..utils.tunnel import NgrokTunnel

from ..backend.blockio import clean_blockio_test_wallet

logger = logging.getLogger(__name__)


class BlockIoBTCTestCase(CoinTestCase, unittest.TestCase):
    """ Test that our BTC accounting works on top of block.io API. """

    test_wallet_cleaned = False

    def setup_receiving(self, wallet):

        # We need ngrok tunnel for webhook notifications
        self.ngrok = NgrokTunnel(11211)

        # Pass dynamically generated tunnel URL to backend config
        tunnel_url = self.ngrok.start()
        self.backend.walletnotify_config["url"] = tunnel_url
        self.backend.walletnotify_config["port"] = 11211

        self.incoming_transactions_runnable = self.backend.setup_incoming_transactions(self.app.conflict_resolver, self.app.event_handler_registry)

        self.incoming_transactions_runnable.start()

    def teardown_receiving(self):

        incoming_transactions_runnable = getattr(self, "incoming_transactions_runnable", None)
        if incoming_transactions_runnable:
            incoming_transactions_runnable.stop()

        danglingthreads.check_dangling_threads()

        self.ngrok.stop()

    def clean_test_wallet(self):
        """Make sure the test wallet does't become unmanageable on block.io backend."""
        if not self.test_wallet_cleaned:
            clean_blockio_test_wallet(self.backend, balance_threshold=Decimal(5000) / Decimal(10**8))
            self.test_wallet_cleaned = True

    def setup_coin(self):

        test_config = os.path.join(os.path.dirname(__file__), "blockio-bitcoin.config.yaml")
        self.assertTrue(os.path.exists(test_config), "Did not found {}".format(test_config))
        self.configurator.load_yaml_file(test_config)

        coin = self.app.coins.get("btc")
        self.backend = coin.backend

        self.Address = coin.address_model
        self.Wallet = coin.wallet_model
        self.Transaction = coin.transaction_model
        self.Account = coin.account_model
        self.NetworkTransaction = coin.network_transaction_model

        self.external_transaction_confirmation_count = 1

        # Withdrawal amounts must be at least 0.00002000 BTCTEST, and at most 50.00000000 BTCTEST.
        self.external_send_amount = Decimal(2100) / Decimal(10**8)
        self.network_fee = Decimal(1000) / Decimal(10**8)

        # Wait 15 minutes for 1 confimation from the BTC TESTNET
        self.external_receiving_timeout = 60 * 20

        self.clean_test_wallet()


class BlockIoDogeTestCase(BlockIoBTCTestCase):
    """Test that our Dogecoin accounting works on top of block.io API."""

    def setup_coin(self):

        test_config = os.path.join(os.path.dirname(__file__), "blockio-dogecoin.config.yaml")
        self.assertTrue(os.path.exists(test_config), "Did not found {}".format(test_config))
        self.configurator.load_yaml_file(test_config)

        coin = self.app.coins.get("doge")
        self.backend = coin.backend

        self.Address = coin.address_model
        self.Wallet = coin.wallet_model
        self.Transaction = coin.transaction_model
        self.Account = coin.account_model
        self.NetworkTransaction = coin.network_transaction_model

        # Withdrawal amounts must be at least 0.00002000 BTCTEST, and at most 50.00000000 BTCTEST.
        self.external_send_amount = Decimal("2")
        self.network_fee = Decimal("1")

        # for test_send_receive_external() the confirmation
        # count before we let the test pass
        self.external_transaction_confirmation_count = 2

        # Wait 3 minutes for 1 confimation from the BTC TESTNET
        self.external_receiving_timeout = 60 * 10

        self.clean_test_wallet()

