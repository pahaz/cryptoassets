import os
import transaction
import time

from sqlalchemy.exc import IntegrityError
from pyramid import testing

from ..models import DBSession
from ..models import NotEnoughAccountBalance


class CoinTestCase:
    """ Base class for different tests. """

    def setUp(self):

        self.config = testing.setUp()

        self.Address = None
        self.Transaction = None
        self.Wallet = None
        self.Account = None
        self.setup_coin()

    def setup_coin(self):
        raise NotImplementedError()

    def setup_test_find_address(self, wallet, acount):
        raise NotImplementedError()

    def tearDown(self):
        DBSession.remove()
        testing.tearDown()

    def test_create_address(self):
        """ Creates a new wallet and fresh bitcoin address there. """

        with transaction.manager:
            wallet = self.Wallet()
            DBSession.add(wallet)

            account = wallet.create_account("Test account")
            address = wallet.create_receiving_address(account, "Test address {}".format(time.time()))

            # TODO: Check for valid bitcoin addresss
            self.assertGreater(len(address.address), 10)

    def test_create_account(self):
        """ Creates a new wallet and fresh bitcoin address there. """

        with transaction.manager:
            wallet = self.Wallet()
            DBSession.add(wallet)

            # Must flush before we refer to wallet pk
            DBSession.flush()

            account = wallet.create_account("Test account")
            self.assertEqual(account.balance, 0)

    def test_send_internal(self):
        """ Creates a new wallet and fresh bitcoin address there. """

        with transaction.manager:
            wallet = self.Wallet()
            DBSession.add(wallet)
            DBSession.flush()

            sending_account = wallet.create_account("Test account")
            receiving_account = wallet.create_account("Test account 2")
            DBSession.flush()
            sending_account.balance = 100

            wallet.send_internal(sending_account, receiving_account, 100, "Test transaction")
            self.assertEqual(receiving_account.balance, 100)
            self.assertEqual(sending_account.balance, 0)

    def test_send_internal_low_balance(self):
        """ Does internal transaction where balance requirement is not met. """

        with transaction.manager:
            wallet = self.Wallet()
            DBSession.add(wallet)
            DBSession.flush()
            sending_account = wallet.create_account("Test account")
            receiving_account = wallet.create_account("Test account 2")
            sending_account.balance = 100
            DBSession.flush()
            assert sending_account.id

            def test():
                wallet.send_internal(sending_account, receiving_account, 110, "Test transaction")

            self.assertRaises(NotEnoughAccountBalance, test)

    def test_cannot_import_existing_address(self):
        """ Do not allow importing an address which already exists. """

        def test():

            with transaction.manager:
                wallet = self.Wallet()
                DBSession.add(wallet)

                account = wallet.create_account("Test account")
                address = wallet.create_receiving_address(account, "Test address {}".format(time.time()))
                self.assertEqual(DBSession.query(self.Address.id).count(), 1)

                wallet.add_address(account, "Test import {}".format(time.time()), address.address)

                # Should not be reached
                self.assertEqual(DBSession.query(self.Address.id).count(), 1)

        self.assertRaises(IntegrityError, test)

    def test_refresh_account_balance(self):
        """ Read the external balance to an account. """
        with transaction.manager:
            wallet = self.Wallet()
            DBSession.add(wallet)
            DBSession.flush()
            account = wallet.create_account("Test account")
            self.setup_test_fund_address(wallet, account)
            wallet.refresh_account_balance(account)

            # Assume we have at least 5 TESTNET bitcoins there
            self.assertGreater(account.balance, 5)

    def test_send_external(self):
        """ Receives Bitcoins from external address """
        with transaction.manager:
            wallet = self.Wallet()
            DBSession.add(wallet)
            DBSession.flush()
            account = wallet.create_account("Test account")

            # Sync wallet with the external balance
            wallet.refresh_account_balance(account)

            receiving_address = wallet.create_receiving_address(account, "Test address {}".format(time.time()))

            # Send Bitcoins through BlockChain
            # wallet.send_external(account, receiving_address.address, 2100, "Test send {}".format(time.time()))



