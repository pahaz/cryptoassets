import os
import unittest
import time

import transaction
from sqlalchemy import create_engine

from ..models import DBSession
from ..models import Base
from ..backend import registry as backendregistry

from ..backend.blockio import BlockIo
from ..backend.blockio import SochainMonitor
from ..backend.blockio import _convert_to_satoshi
from ..backend.blockio import _convert_to_decimal
from ..backend import registry as backendregistry
from ..lock.simple import create_thread_lock


from .base import CoinTestCase


class BlockIoBTCTestCase(CoinTestCase, unittest.TestCase):

    def setup_receiving(self, wallet):

        # Print out exceptions in Pusher messaging
        from websocket._core import enableTrace
        enableTrace(True)

        self.backend.monitor = SochainMonitor(self.backend, [wallet], os.environ["PUSHER_API_KEY"], "btctest")

    def teardown_receiving(self):
        if self.backend.monitor:
            self.backend.monitor.close()

    def setup_coin(self):

        self.backend = BlockIo("btc", os.environ["BLOCK_IO_API_KEY"], os.environ["BLOCK_IO_PIN"], create_thread_lock)
        backendregistry.register("btc", self.backend)
        self.monitor = None

        # We cannot use :memory db as,
        # SQLite does not support multithread access for it
        # http://stackoverflow.com/a/15681692/315168

        engine = create_engine('sqlite:///unittest.sqlite', echo=False)
        from ..coin.bitcoin.models import BitcoinWallet
        from ..coin.bitcoin.models import BitcoinAddress
        from ..coin.bitcoin.models import BitcoinTransaction
        from ..coin.bitcoin.models import BitcoinAccount
        DBSession.configure(bind=engine)
        Base.metadata.create_all(engine)

        self.Address = BitcoinAddress
        self.Wallet = BitcoinWallet
        self.Transaction = BitcoinTransaction
        self.Account = BitcoinAccount

        # Withdrawal amounts must be at least 0.00002000 BTCTEST, and at most 50.00000000 BTCTEST.
        self.external_send_amount = 2100
        self.network_fee = 1000

    def setup_test_fund_address(self, wallet, account):
        # Import some TESTNET coins
        wallet.add_address(account, "Test import {}".format(time.time()), os.environ["BLOCK_IO_TESTNET_TEST_FUND_ADDRESS"])

    def is_address_monitored(self, wallet, address):
        """ Check if we can get notifications from an incoming transactions for a certain address.

        :param wallet: Wallet object

        :param address: Address object
        """
        if len(wallet.backend.monitor.wallets) == 0:
            return False

        return address.address in wallet.backend.monitor.wallets[wallet.id]["addresses"]

    def test_convert(self):
        """ Test amount conversions. """
        v = _convert_to_satoshi("1")
        v2 = _convert_to_decimal(v)
        self.assertEqual(float(v2), 1.0)

    def test_store_all_the_satoshis(self):
        """ See that we can correctly store very big amount of satoshi on the account. """
        v = _convert_to_satoshi("21000000")

        with transaction.manager:
            wallet = self.Wallet()
            DBSession.add(wallet)

            account = wallet.create_account("Test account")
            account.balance = v

        with transaction.manager:
            account = DBSession.query(self.Account).first()
            self.assertEqual(account.balance, v)


class BlockIoDogeTestCase(CoinTestCase, unittest.TestCase):

    def setup_test_fund_address(self, wallet, account):
        # Import some TESTNET coins
        wallet.add_address(account, "Test import {}".format(time.time()), os.environ["BLOCK_IO_DOGE_TESTNET_TEST_FUND_ADDRESS"])

    def setup_coin(self):

        backendregistry.register("doge", BlockIo("doge", os.environ["BLOCK_IO_API_KEY_DOGE"], os.environ["BLOCK_IO_PIN"], create_thread_lock))

        engine = create_engine('sqlite://')
        from ..coin.dogecoin.models import DogeWallet
        from ..coin.dogecoin.models import DogeAddress
        from ..coin.dogecoin.models import DogeTransaction
        from ..coin.dogecoin.models import DogeAccount
        DBSession.configure(bind=engine)
        Base.metadata.create_all(engine)

        self.Address = DogeAddress
        self.Wallet = DogeWallet
        self.Transaction = DogeTransaction
        self.Account = DogeAccount

        # Withdrawal amounts must be at least 0.00002000 BTCTEST, and at most 50.00000000 BTCTEST.
        self.external_send_amount = 100
        self.network_fee = 1


