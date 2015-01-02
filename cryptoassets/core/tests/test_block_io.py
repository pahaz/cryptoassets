import os
import unittest
import time
import logging
from decimal import Decimal

import pytest

from ..models import _now

from .base import CoinTestCase
from .base import has_inet
from . import danglingthreads

logger = logging.getLogger(__name__)


#: This is a known address in the testnet test wallet with some funds on it
BLOCK_IO_TESTNET_TEST_FUND_ADDRESS = "2MsgW3kCrRFtJuo9JNjkorWXaZSvLk4EWRr"


class BlockIoBTCTestCase(CoinTestCase, unittest.TestCase):
    """ Test that our BTC accounting works on top of block.io API. """

    def setup_receiving(self, wallet):

        # Print out exceptions in Pusher messaging
        from websocket._core import enableTrace

        logger = logging.getLogger()
        if logger.level < logging.WARN:
            enableTrace(True)

        self.incoming_transactions_runnable = self.backend.setup_incoming_transactions(self.app.conflict_resolver, self.app.notifiers)

        self.incoming_transactions_runnable.start()

    def teardown_receiving(self):

        incoming_transactions_runnable = getattr(self, "incoming_transactions_runnable", None)
        if incoming_transactions_runnable:
            incoming_transactions_runnable.stop()

        danglingthreads.check_dangling_threads()

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

        self.external_transaction_confirmation_count = 1

        # Withdrawal amounts must be at least 0.00002000 BTCTEST, and at most 50.00000000 BTCTEST.
        self.external_send_amount = Decimal(2100) / Decimal(10**8)
        self.network_fee = Decimal(1000) / Decimal(10**8)

        # Wait 15 minutes for 1 confimation from the BTC TESTNET
        self.external_receiving_timeout = 60 * 20

    def is_address_monitored(self, wallet, address):
        """ Check if we can get notifications from an incoming transactions for a certain address.

        :param wallet: Wallet object

        :param address: Address object
        """

        if len(self.incoming_transactions_runnable.wallets) == 0:
            return False

        return address.address in self.incoming_transactions_runnable.wallets[wallet.id]["addresses"]

    def wait_receiving_address_ready(self, wallet, receiving_address):

        # Let the Pusher to build the connection
        # Make sure SoChain started to monitor this address
        deadline = time.time() + 15
        while time.time() < deadline:
            if self.is_address_monitored(wallet, receiving_address):
                break

        self.assertTrue(self.is_address_monitored(wallet, receiving_address), "The receiving address didn't become monitored {}".format(receiving_address.address))

    def test_get_active_transactions(self):
        """ Query for the list of unconfirmed transactions.
        """

        # Spoof three transactions
        # - one internal
        # - one external, confirmed
        # - one external, unconfirmed
        #

        with self.app.conflict_resolver.transaction() as session:
            wallet = self.Wallet()
            session.add(wallet)
            session.flush()

            account = wallet.create_account("Test account")
            session.flush()

            address = wallet.create_receiving_address(account, "Test address {}".format(time.time()))
            session.flush()

            # internal
            t = wallet.Transaction()
            t.sending_account = account
            t.receiving_account = account
            t.amount = 1000
            t.wallet = wallet
            t.credited_at = _now()
            t.label = "tx1"
            session.add(t)

            # external, confirmed
            t = wallet.Transaction()
            t.sending_account = None
            t.receiving_account = account
            t.amount = 1000
            t.wallet = wallet
            t.credited_at = _now()
            t.label = "tx2"
            t.txid = "txid2"
            t.confirmations = 6
            t.address = address
            session.add(t)

            # external, unconfirmed
            t = wallet.Transaction()
            t.sending_account = None
            t.receiving_account = account
            t.amount = 1000
            t.wallet = wallet
            t.credited_at = None
            t.label = "tx3"
            t.txid = "txid3"
            t.confirmations = 1
            t.address = address
            session.add(t)

            session.flush()

            external_txs = wallet.get_external_received_transactions()
            self.assertEqual(external_txs.count(), 2)

            active_txs = wallet.get_active_external_received_transcations()
            self.assertEqual(active_txs.count(), 1)
            self.assertEqual(active_txs.first().txid, "txid3")
            self.assertEqual(active_txs.first().address.id, address.id)


class BlockIoDogeTestCase(BlockIoBTCTestCase):

    def setup_coin(self):

        test_config = os.path.join(os.path.dirname(__file__), "blockio-dogecoin.config.yaml")
        self.assertTrue(os.path.exists(test_config), "Did not found {}".format(test_config))
        self.configurator.load_yaml_file(test_config)

        coin = self.app.coins.get("btc")
        self.backend = coin.backend

        self.Address = coin.address_model
        self.Wallet = coin.wallet_model
        self.Transaction = coin.transaction_model
        self.Account = coin.account_model

        # Withdrawal amounts must be at least 0.00002000 BTCTEST, and at most 50.00000000 BTCTEST.
        self.external_send_amount = Decimal("2")
        self.network_fee = Decimal("1")

        # for test_send_receive_external() the confirmation
        # count before we let the test pass
        self.external_transaction_confirmation_count = 2

        # Wait 3 minutes for 1 confimation from the BTC TESTNET
        self.external_receiving_timeout = 60 * 5
