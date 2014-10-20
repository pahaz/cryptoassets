import os
import unittest
import time

from sqlalchemy import create_engine

from ..models import DBSession
from ..models import Base
from ..backend import registry as backendregistry

from ..backend.blockio import BlockIo
from ..backend.blockio import _convert_to_satoshi
from ..backend.blockio import _convert_to_decimal
from ..backend import registry as backendregistry
from ..lock.simple import create_thread_lock


from .base import CoinTestCase


class BlockIoBTCTestCase(CoinTestCase, unittest.TestCase):

    def setup_coin(self):

        backendregistry.register("btc", BlockIo(os.environ["BLOCK_IO_API_KEY"], os.environ["BLOCK_IO_PIN"], create_thread_lock))

        engine = create_engine('sqlite://')
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

    def setup_test_fund_address(self, wallet, account):
        # Import some TESTNET coins
        wallet.add_address(account, "Test import {}".format(time.time()), os.environ["BLOCK_IO_TESTNET_TEST_FUND_ADDRESS"])

    def test_convert(self):
        """ Test amount conversions. """
        v = _convert_to_satoshi("1")
        v2 = _convert_to_decimal(v)
        self.assertEqual(float(v2), 1.0)

class BlockIoDogeTestCase(CoinTestCase, unittest.TestCase):

    def setup_test_fund_address(self, wallet, account):
        # Import some TESTNET coins
        wallet.add_address(account, "Test import {}".format(time.time()), os.environ["BLOCK_IO_TESTNET_TEST_FUND_ADDRESS"])

    def setup_coin(self):

        backendregistry.register("doge", BlockIo(os.environ["BLOCK_IO_API_KEY_DOGE"], os.environ["BLOCK_IO_PIN"], create_thread_lock))

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

