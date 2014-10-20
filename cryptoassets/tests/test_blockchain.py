import os
import unittest
import time

from sqlalchemy import create_engine

from ..models import DBSession
from ..models import Base
from ..backend import registry as backendregistry

from ..backend.blockchain import BlockChain
from ..backend import registry as backendregistry
from ..lock.simple import create_thread_lock


from .base import CoinTestCase


class BlockChainBTCTestCase(CoinTestCase, unittest.TestCase):

    def setup_coin(self):

        backendregistry.register("btc", BlockChain(os.environ["BLOCKCHAIN_IDENTIFIER"], os.environ["BLOCKCHAIN_PASSWORD"], create_thread_lock))

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
        wallet.add_address(account, "Test import {}".format(time.time()), os.environ["BLOCKCHAIN_TESTNET_TEST_FUND_ADDRESS"])
