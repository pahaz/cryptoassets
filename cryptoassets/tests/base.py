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

        # How many satoshis we use in send_external()
        self.external_send_amount = 100
        self.network_fee = 1000

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
            DBSession.flush()
            account = wallet.create_account("Test account")
            DBSession.flush()
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

            # We should have created one transaction
            self.assertEqual(DBSession.query(self.Transaction.id).count(), 1)
            tx = DBSession.query(self.Transaction).first()
            self.assertEqual(tx.sending_account, sending_account.id)
            self.assertEqual(tx.receiving_account, receiving_account.id)

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
                DBSession.flush()
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
            DBSession.flush()
            self.setup_test_fund_address(wallet, account)
            wallet.refresh_account_balance(account)

            # Assume we have at least 5 TESTNET bitcoins there
            self.assertIsNot(account.balance, 0, "Account balance was zero after refresh_account_balance()")
            self.assertGreater(account.balance, 5)

    def test_send_external(self):
        """ Send Bitcoins from external address """
        with transaction.manager:
            wallet = self.Wallet()
            DBSession.add(wallet)
            DBSession.flush()
            account = wallet.create_account("Test account")
            DBSession.flush()
            # Sync wallet with the external balance
            self.setup_test_fund_address(wallet, account)
            wallet.refresh_account_balance(account)

            receiving_address = wallet.create_receiving_address(account, "Test address {}".format(time.time()))

            # Send Bitcoins through BlockChain
            wallet.send_external(account, receiving_address.address, self.external_send_amount, "Test send {}".format(time.time()))

            # We should have created one transaction
            # which is not broadcasted yet
            self.assertEqual(DBSession.query(self.Transaction.id).count(), 1)
            tx = DBSession.query(self.Transaction).first()
            self.assertEqual(tx.sending_account, account.id)
            self.assertEqual(tx.receiving_account, None)
            self.assertEqual(tx.state, "pending")
            self.assertEqual(tx.txid, None)
            self.assertIsNone(tx.processed_at)
            wallet.broadcast()

            self.assertEqual(tx.state, "broadcasted")
            self.assertIsNotNone(tx.txid)
            self.assertIsNotNone(tx.processed_at)

    def test_charge_network_fee(self):
        """ Do an external transaction and see we account network fees correctly. """

        with transaction.manager:
            wallet = self.Wallet()
            DBSession.add(wallet)
            DBSession.flush()
            account = wallet.create_account("Test account")
            DBSession.flush()

            # Sync wallet with the external balance
            self.setup_test_fund_address(wallet, account)
            wallet.refresh_account_balance(account)

            receiving_address = wallet.create_receiving_address(account, "Test address {}".format(time.time()))

            # Send Bitcoins through BlockChain
            wallet.send_external(account, receiving_address.address, self.external_send_amount, "Test send {}".format(time.time()))
            wallet.broadcast()

            # Our fee account goes below zero, because network fees
            # are subtracted from there
            fee_account = wallet.get_or_create_network_fee_account()
            self.assertLess(fee_account.balance, 0)

            fee_txs = DBSession.query(self.Transaction).filter(self.Transaction.state == "network_fee")
            self.assertEqual(fee_txs.count(), 1)
            self.assertEqual(fee_txs.first().amount, self.network_fee)

    def test_broadcast_no_transactions(self):
        """ Broadcast must not fail even we don't have any transactions. """

        with transaction.manager:
            wallet = self.Wallet()
            DBSession.add(wallet)
            wallet.broadcast()

    def test_receive_external_spoofed(self):
        """ Test receiving external transaction.

        Don't actually receive anything, spoof the incoming transaction.
        """

        with transaction.manager:
            wallet = self.Wallet()
            DBSession.add(wallet)
            DBSession.flush()

            account = wallet.create_account("Test account")
            DBSession.flush()
            receiving_address = wallet.create_receiving_address(account, "Test address {}".format(time.time()))
            txid = "fakefakefakefake"
            wallet.receive(txid, receiving_address.address, 1000, dict(confirmations=0))

            # First we should just register the transaction
            txs = DBSession.query(self.Transaction).filter(self.Transaction.state == "incoming")
            self.assertEqual(txs.count(), 1)
            self.assertEqual(txs.first().amount, 1000)
            self.assertFalse(txs.first().is_confirmed())
            self.assertEqual(account.balance, 0)
            self.assertEqual(wallet.balance, 0)
            self.assertIsNone(txs.first().processed_at)

            # Exceed the confirmation threshold
            wallet.receive(txid, receiving_address.address, 1000, dict(confirmations=6))
            self.assertTrue(txs.first().is_confirmed())
            self.assertEqual(account.balance, 1000)
            self.assertEqual(wallet.balance, 1000)
            self.assertIsNone(txs.first().processed_at)

            # Mark the transaction as processed the transaction
            wallet.mark_transaction_processed(txs.first().id)

            txs = DBSession.query(self.Transaction).filter(self.Transaction.state == "processed")
            self.assertEqual(txs.count(), 1)
            self.assertIsNotNone(txs.first().processed_at)
