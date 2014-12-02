"""bitcoind and bitcoind-likes backend.

Created upon https://github.com/4tar/python-bitcoinrpc/tree/p34-compatablity

Developer reference: https://bitcoin.org/en/developer-reference#bitcoin-core-apis

Original API call list: https://en.bitcoin.it/wiki/Original_Bitcoin_client/API_calls_list
"""

import logging
import transaction
import datetime
import socket
from decimal import Decimal

from collections import Counter

from zope.dottedname.resolve import resolve

from bitcoinrpc.authproxy import AuthServiceProxy
from bitcoinrpc.authproxy import JSONRPCException

from .base import CoinBackend

from .pipe import PipedWalletNotifyHandler

from ..coin.registry import Coin
from ..notify import events
from ..notify.registry import NotifierRegistry

logger = logging.getLogger(__name__)


class BitcoindJSONError(Exception):
    pass


class BitcoindDerivate(CoinBackend):
    """ Bitcoind or another altcoin using bitcoind-like JSON-RPC. """


class Bitcoind(BitcoindDerivate):
    """Backend for the original bitcoind (BTC) itself."""

    def __init__(self, coin, url, walletnotify=None):
        """
        :param coin: cryptoassets.core.coin.registry.Coin instacne
        :param url: bitcoind connection url
        :param wallet_notify: Wallet notify configuration
        """

        assert isinstance(coin, Coin)

        self.url = url
        self.bitcoind = AuthServiceProxy(url)
        self.coin = coin
        self.default_confirmations = 3

        # Bitcoind has its internal accounting. We put all balances on this specific account
        self.bitcoind_account_name = "cryptoassets"

        # How many confirmations inputs must when we are spending bitcoins.
        self.bitcoind_send_input_confirmations = 1

        self.walletnotify_config = walletnotify

    def to_internal_amount(self, amount):
        return Decimal(amount)

    def to_external_amount(self, amount):
        return Decimal(amount)

    def api_call(self, name, *args, **kwargs):
        """ """
        try:
            func = getattr(self.bitcoind, name)
            result = func(*args, **kwargs)
            return result
        except ValueError as e:
            #
            raise BitcoindJSONError("Probably could not authenticate against bitcoind-like RPC, try manually with curl") from e
        except socket.timeout as e:
            raise BitcoindJSONError("Got timeout when doing bitcoin RPC call {}. Maybe bitcoind was not synced with network?".format(name)) from e
        except JSONRPCException as e:
            msg = e.error.get("message")
            if msg:
                # Show error message for more pleasant debugging
                raise BitcoindJSONError("Error communicating with bitcoind API call {}: {}".format(name, msg)) from e
            # Didn't have specific error message
            raise

    def import_private_key(self, label, private_key):
        """Import an existing private key to this daemon.

        This does not do balance refresh.

        :param string: public_address Though we could derive public address from the private key, for now we do a shortcut here and add it as is.
        """
        result = self.api_call("importprivkey", private_key, label, False)

    def create_address(self, label):
        """ Create a new receiving address.
        """

        # TODO: Bitcoind doesn't internally support
        # labeled addresses

        result = self.api_call("getnewaddress", self.bitcoind_account_name)
        return result

    def refresh_account(self, account):
        """Update the balances of an account.
        """

    def get_balances(self, addresses):
        """ Get balances on multiple addresses.
        """
        raise NotImplementedError()

    def get_received_by_address(self, address, confirmations=None):
        """
        """
        if confirmations is None:
            confirmations = self.default_confirmations

        assert type(confirmations) == int
        result = self.api_call("getreceivedbyaddress", address, confirmations)

        return _convert_to_satoshi(result)

    def list_transactions(self, start, limit):
        """
        """
        result = self.api_call("listtransactions", self.bitcoind_account_name, limit, start)
        return result

    def get_transaction(self, txid):
        """ """
        return self.api_call("gettransaction", txid)

    def get_lock(self, name):
        """ Create a named lock to protect the operation. """
        raise NotImplementedError()

    def send(self, recipients, label):
        """ Broadcast outgoing transaction.

        This is called by send/receive process.

        :param recipients: Dict of (address, internal amount)
        """
        amounts = {}
        for address, satoshis in recipients.items():
            amounts[address] = float(self.to_external_amount(satoshis))

        txid = self.api_call("sendmany", self.bitcoind_account_name, amounts, self.bitcoind_send_input_confirmations, label)

        # 'amount': Decimal('0E-8'), 'timereceived': 1416583349, 'fee': Decimal('-0.00010000'), 'txid': 'bf0decbc5726e75afdf9768dbbf611ae6ba52e3b36dbd96aecb3de2728ef8ebb', 'details': [{'category': 'send', 'address': 'mhShYyZhFgAmLwjaKyN2hN3HVt78a3BrtP', 'account': 'cryptoassets', 'amount': Decimal('-0.00002100'), 'fee': Decimal('-0.00010000')}, {'category': 'receive', 'address': 'mhShYyZhFgAmLwjaKyN2hN3HVt78a3BrtP', 'account': 'cryptoassets', 'amount': Decimal('0.00002100')}], 'confirmations': 0, 'hex': '0100000001900524bfa2d0ac8a361900b54fb8eb09287c9e4585cb446e66914f0db81dd36f000000006a473044022064210bad81028559d110a71142b29ce38ff13c1d712aa200913e3300b91b9ff7022050acbf3393443796104f38dd349b5dce1a12bec7e64308c7ec9f491476e8b9cc0121026a3dead5584ed1afa7f754ce8cb027be91ef418d7ddd7085fd690ad8a8d2196effffffff021c276c00000000001976a9141e966ad7ac7570fbd1d9d977fc382a9565c6bd3188ac34080000000000001976a914152247f71eaf81783197e357907857aecdb44bcb88ac00000000', 'walletconflicts': [], 'time': 1416583349}
        txdata = self.api_call("gettransaction", txid)
        for detail in txdata["details"]:
            if detail["category"] == "send":
                fee = -1 * self.to_internal_amount(detail["fee"])

        return txid, fee

    def monitor_address(self, address):
        pass

    def create_transaction_updater(self, session, notifiers):
        tx_updater = TransactionUpdater(session, self, self.coin, notifiers)
        return tx_updater

    def setup_incoming_transactions(self, dbsession, notifiers):
        """Create a named pipe walletnotify handler.
        """
        config = self.walletnotify_config

        if not config:
            return

        config = config.copy()

        transaction_updater = self.create_transaction_updater(dbsession, notifiers)

        klass = config.pop("class")
        provider = resolve(klass)
        config["transaction_updater"] = transaction_updater
        # Pass given configuration options to the backend as is
        try:
            handler = provider(**config)
        except TypeError as te:
            # TODO: Here we reflect potential passwords from the configuration file
            # back to the terminal
            # TypeError: __init__() got an unexpected keyword argument 'network'
            raise ConfigurationError("Could not initialize backend {} with options {}".format(klass, data)) from te

        return handler


class BadWalletNotify(Exception):
    pass


class TransactionUpdater:
    """Write transactions updates from bitcoind to the database."""

    def __init__(self, session, backend, coin, notifiers):
        """
        :param session: SQLAlchemy database session
        """
        assert isinstance(coin, Coin)

        self.backend = backend
        self.coin = coin
        self.session = session

        # Simple book-keeping of number of transactions we have handled
        self.count = 0

        #: UTC timestamp when we got the last transaction notification
        self.last_wallet_notify = None

        if notifiers:
            assert isinstance(notifiers, NotifierRegistry)
            #: Notifiers registry we are going to inform about transaction status updates
            self.notifiers = notifiers
        else:
            self.notifiers = None

    def handle_wallet_notify(self, txid, transaction_manager):
        """Incoming walletnotify event.

        :parma txid: Bitcoin network transaction hash

        :param transaction_manager: Transaction manager instance which will be used to isolate each transaction update commit
        """
        self.last_wallet_notify = datetime.datetime.utcnow()

        txdata = self.backend.get_transaction(txid)

        # ipdb> print(txdata)
        # {'blockhash': '00000000cb7b5d9fed3316cceec1af71b941b77ce0b0588c98a34f05bd292b6f', 'time': 1415201940, 'timereceived': 1416370475, 'details': [{'account': 'test', 'address': 'n23pUFwzyVUXd7t4nZLzkZoidbjNnbQLLr', 'amount': Decimal('1.20000000'), 'category': 'receive'}], 'blockindex': 6, 'walletconflicts': [], 'amount': Decimal('1.20000000'), 'confirmations': 2848, 'txid': 'bfb0ef36cdf4c7ec5f7a33ed2b90f0267f2d91a4c419bcf755cc02d6c0176ebf', 'hex': '01000000017b0fedcafed339974e892f2a6da74e6e35789a60cf6efbf23b9059c346e33f32010000006b483045022100fce7ce10797c4a0bd56d5e64dc0fa1e5d3cdba4b495e2a8d76d9c43e1790d82302207b885373d9fc8dbf08165fd24250174344d6792207d98f051c98280b5a1720510121021f8ab4e791c159ba43a2d45464312f7cbafee6cd6bbcdaafb26b545e1deecf64ffffffff0234634e3e090000001976a9141a257a2ef0e6821f314d074f84a4ece9274d7e9488ac000e2707000000001976a914e138e119752bdd89cf8b46ff283181398d85b55288ac00000000', 'blocktime': 1415201940}

        # Sum together received per address
        addresses = Counter()  # address -> amount mapping
        for detail in txdata["details"]:
            if detail["category"] == "receive":
                addresses[detail["address"]] += self.backend.to_internal_amount(detail["amount"])

        # Pass confirmations in the extra transaction details
        extra = dict(confirmations=txdata["confirmations"])

        # See which address our wallet knows about
        # wallet = self.session.query(self.wallet_class).get(self.wallet_id)
        # if not wallet:
        #     raise RuntimeError("Transaction updater could not find wallet with wallet id {}".format(self.wallet_id))

        Address = self.coin.address_model

        for address, amount in addresses.items():

            transaction_id = None
            account_id = None
            confirmations = None

            with transaction_manager:
                address_obj = self.session.query(Address).filter(Address.address == address).first()  # noqa

                if address_obj:
                    wallet = address_obj.account.wallet
                    account, transaction = wallet.receive(txid, address, amount, extra)
                    confirmations = transaction.confirmations
                    logger.info("Wallet notify account %d, address %s, amount %s, tx confirmations %d", account.id, address, amount, confirmations)

                    # This will cause Transaction instance to get its id
                    self.session.flush()

                    account_id = account.id
                    transaction_id = transaction.id

                else:
                    logger.info("Skipping transaction notify for unknown address %s, amount %s", address, amount)

            # Tranasactipn is committed in this point, notify the application about the new data in the database
            if transaction_id:
                logger.info("Starting txupdate notify")
                if self.notifiers:
                    event_name, data = events.create_txupdate(txid=txid, transaction=transaction_id, account=account_id, address=address, amount=amount, confirmations=confirmations)
                    self.notifiers.notify(event_name, data)
            else:
                logger.info("No transaction object was created")

        self.count += 1

    def rescan_address(self, address, confirmations):
        """
        :param address: Address object
        """
        balance = self.backend.to_internal_amount(self.backend.listreceivedbyaddress(address.address, confirmations, False))
        if balance != address.balance:
            # Uh oh, our internal bookkeeping is not up-to-date with address,
            # need full rescan
            pass

    def rescan_all(self, transaction_manager):
        """Rescan all transactions in a wallet to see if we have miss any.

        TODO: Currently this does not correctly subtract outgoing transactions

        :return: int, number of total transactions found for the wallet
        """

        found = 0
        batch_size = 100
        current = 0

        txs = self.backend.list_transactions(current, batch_size)

        while txs:

            logger.info("Rescanning transactions from %d to %d", current, current + batch_size)

            for tx in txs:
                # TODO See if we can optimize this pulling all tx data from listransactions information without need to do one extra JSON-RPC per tx
                self.handle_wallet_notify(tx["txid"], transaction_manager)
                self.count += 1
                found += 1

            current += batch_size
            txs = self.backend.list_transactions(current, batch_size)

        return found
