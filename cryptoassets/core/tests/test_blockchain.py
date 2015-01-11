import os
import unittest
import time

from sqlalchemy import create_engine

import pytest

from ..models import Base

from ..backend.blockchain import BlockChain

from .base import CoinTestCase


@pytest.mark.skipif(True, reason="blockchain.info support currently disabled")
class BlockChainBTCTestCase(CoinTestCase, unittest.TestCase):

    def setup_coin(self):

        backendregistry.register("btc", BlockChain(os.environ["BLOCKCHAIN_IDENTIFIER"], os.environ["BLOCKCHAIN_PASSWORD"]))

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

        self.external_transaction_confirmation_count = 0

        # Withdrawal amounts must be at least 0.00002000 BTCTEST, and at most 50.00000000 BTCTEST.
        self.external_send_amount = 2100
        self.network_fee = 1000
        # Wait 10 minutes for 1 confimation from the BTC TESTNET
        self.external_receiving_timeout = 60 * 10

    def setup_test_fund_address(self, wallet, account):
        # Import some TESTNET coins
        wallet.add_address(account, "Test import {}".format(time.time()), os.environ["BLOCKCHAIN_TESTNET_TEST_FUND_ADDRESS"])

    def test_send_receive_external(self):
        # Not implemented
        pass