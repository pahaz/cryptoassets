import os
import unittest
import transaction
import time

from pyramid import testing

from .models import DBSession
from .models import Base
from .models import NotEnoughBalance
from .backend.blockio import BlockIo
from .backend import registry as backendregistry


from paste.deploy.loadwsgi import appconfig


class TestBlockIO(unittest.TestCase):

    def setUp(self):

        self.config = testing.setUp()
        from sqlalchemy import create_engine
        engine = create_engine('sqlite://')

        backendregistry.register("btc", BlockIo(os.environ["BLOCKIO_API_KEY"], os.environ["BLOCKIO_PIN"]))

        from .bitcoin.models import BitcoinAccount
        from .bitcoin.models import BitcoinAddress
        from .bitcoin.models import BitcoinTransaction
        from .bitcoin.models import BitcoinWallet

        DBSession.configure(bind=engine)
        Base.metadata.create_all(engine)

    def tearDown(self):
        DBSession.remove()
        testing.tearDown()

    def test_create_address(self):
        """ Creates a new wallet and fresh bitcoin address there. """
        from .bitcoin.models import BitcoinWallet

        with transaction.manager:
            wallet = BitcoinWallet()
            DBSession.add(wallet)

            account = wallet.create_account("Test account")
            address = wallet.create_receiving_address(account, "Test address {}".format(time.time()))

            # TODO: Check for valid bitcoin addresss
            self.assertGreater(len(address.address), 10)

    def test_create_account(self):
        """ Creates a new wallet and fresh bitcoin address there. """
        from .bitcoin.models import BitcoinWallet

        with transaction.manager:
            wallet = BitcoinWallet()
            DBSession.add(wallet)

            # Must flush before we refer to wallet pk
            DBSession.flush()

            account = wallet.create_account("Test account")
            self.assertEqual(account.balance, 0)

    def test_send_internal(self):
        """ Creates a new wallet and fresh bitcoin address there. """
        from .bitcoin.models import BitcoinWallet

        with transaction.manager:
            wallet = BitcoinWallet()
            DBSession.add(wallet)
            DBSession.flush()

            sending_account = wallet.create_account("Test account")
            receiving_account = wallet.create_account("Test account 2")
            sending_account.balance = 100

            wallet.send_internal(sending_account, receiving_account, 100, "Test transaction")
            self.assertEqual(receiving_account.balance, 100)
            self.assertEqual(sending_account.balance, 0)

    def test_send_internal_low_balance(self):
        """ Does internal transaction where balance requirement is not met. """
        from .bitcoin.models import BitcoinWallet

        with transaction.manager:
            wallet = BitcoinWallet()
            DBSession.add(wallet)

            sending_account = wallet.create_account("Test account")
            receiving_account = wallet.create_account("Test account 2")
            sending_account.balance = 100

            def test():
                wallet.send_internal(sending_account, receiving_account, 110, "Test transaction")

            self.assertRaises(NotEnoughBalance, test)

    def test_cannot_import_existing_address(self):
        """ Do not allow importing an address which already exists. """
        from .bitcoin.models import BitcoinWallet

        with transaction.manager:
            wallet = BitcoinWallet()
            DBSession.add(wallet)

            account = wallet.create_account("Test account")
            address = wallet.create_receiving_address(account, "Test address {}".format(time.time()))

            def test():
                wallet.import_address(from_account, address.address)

            self.assertRaises(AddressAlreadyExists, test)

    def test_send_receive_external(self):
        """ Receives Bitcoins from external address """
        from .bitcoin.models import BitcoinWallet

        with transaction.manager:
            wallet = BitcoinWallet()
            DBSession.add(wallet)

            from_account = wallet.create_account("Test account")
            to_account = wallet.create_account("Test account 2")
            address = wallet.create_receiving_address(account, "Test address {}".format(time.time()))

            wallet.import_address(from_account, os.ENVIRON["BLOCKIO_TESTNET_TEST_FUND_ADDRESS"])
            wallet.send_external(from_account, )

            # Force balance update
            address.update_balance()




