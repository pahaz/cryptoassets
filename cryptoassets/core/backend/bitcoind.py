"""bitcoind and bitcoind-derivate backend. Interact directly with *bitcoind* service running on your own server.

Because most bitcoin forks have the same `JSON-RPC API <https://en.bitcoin.it/wiki/API_reference_%28JSON-RPC%29>`_ as the original *bitcoind*, you can use this backend for having service for most bitcoind-derived altcoins.

You must configure *bitcoind* on your server to work with *cryptoassets.core*. This happens by editing `bitcoin.conf <https://en.bitcoin.it/wiki/Running_Bitcoin#Bitcoin.conf_Configuration_File>`_.

Example ``bitcoin.conf``::

    # We use bitcoin testnet, not real bitcoins
    testnet=1

    # Enable JSON-RPC
    server=1

    # Username and password
    rpcuser=foo
    rpcpassword=bar

    rpctimeout=5
    rpcport=8332

    # This must be enabled for gettransaction() to work
    txindex=1

    # Send notifications to cryptoassetshelper service over HTTP
    walletnotify=curl --data "txid=%s" http://localhost:28882

.. note ::

    You need to install curl on your server too (sudo apt install curl)

The backend configuration takes following parameters.

:param class: Always ``cryptoassets.core.backend.bitcoind.Bitcoind``

:param url: Bitcoind connection URL with username and password (rpcuser and rpcassword in bitcoin config) for `AuthServiceProxy <https://github.com/jgarzik/python-bitcoinrpc>`_. Usually something like ``http://foo:bar@127.0.0.1:8332/``

:param walletnotify: Dictionary of parameters to set up walletnotify handler.

:param timeout: Timeout for JSON-RPC call. Default is 15 seconds. If the timeout occurs, the API operation can be considered as failed and the bitcoind as dead.

"""

import logging
import datetime
import socket
import time
from decimal import Decimal
from http.client import BadStatusLine
from http.client import CannotSendRequest
from collections import Counter
import threading

from zope.dottedname.resolve import resolve

from bitcoinrpc.authproxy import AuthServiceProxy
from bitcoinrpc.authproxy import JSONRPCException

from . import base

from .pipewalletnotify import PipedWalletNotifyHandler
from .transactionupdater import TransactionUpdater

from ..coin.registry import Coin
from ..event.registry import EventHandlerRegistry

logger = logging.getLogger(__name__)


class BitcoindJSONError(Exception):
    pass


class Bitcoind(base.CoinBackend):
    """Backend for the original bitcoind or its derivates over stock JSON-RPC API.

    Created upon https://github.com/4tar/python-bitcoinrpc/tree/p34-compatablity

    Developer reference: https://bitcoin.org/en/developer-reference#bitcoin-core-apis

    Original API call list: https://en.bitcoin.it/wiki/Original_Bitcoin_client/API_calls_list
    """

    def __init__(self, coin, url, walletnotify=None, timeout=15):
        """
        :param coin: cryptoassets.core.coin.registry.Coin instacne
        :param url: bitcoind connection url
        :param wallet_notify: Wallet notify configuration
        :param timeout: How many seconds wait for the daemon to reply
        """

        assert isinstance(coin, Coin)

        self.url = url
        self.timeout = int(timeout)
        self.coin = coin
        self.default_confirmations = 3

        # Bitcoind has its internal accounting. We put all balances on this specific account
        self.bitcoind_account_name = "cryptoassets"

        # How many confirmations inputs must when we are spending bitcoins.
        self.bitcoind_send_input_confirmations = 1

        self.walletnotify_config = walletnotify

        self.track_incoming_confirmations = True

        self.thread_connection_pool = threading.local()

        #: How many times we try to recover from bad HTTP connection situation
        self.bad_http_connection_retries = 3

    def connect(self, reconnect=False):
        """Gets or creates a per-thread connection to bitcoind.

        Using AuthServiceProxy is thread-unsafe. Because ``CoinBackend`` is accessed from multiple threads, make it safe here.

        https://github.com/petertodd/python-bitcoinlib/issues/35.
        """
        bitcoind = getattr(self.thread_connection_pool, 'bitcoind', None)
        if bitcoind is None or reconnect:

            if bitcoind:
                # XXX: Try to close the existing TCP/IP connection
                logger.warning("Had to reconnect to bitcoind, old connection was %s", bitcoind)

            self.thread_connection_pool.bitcoind = bitcoind = AuthServiceProxy(self.url, timeout=self.timeout)

        return bitcoind

    def require_tracking_incoming_confirmations(self):
        return True

    def to_internal_amount(self, amount):
        return Decimal(amount)

    def to_external_amount(self, amount):
        return Decimal(amount)

    def api_call(self, name, *args, **kwargs):
        """Perform bitcoind JSON-RPC api call.

        Have some safety mechanism to handle most common transportation layer level errors.

        :param name: JSON-RPC function name

        :param args: Passed to underlying bitcoind lib

        :param kwargs: Passed to underlying bitcoind lib
        """

        bitcoind = self.connect()

        for retry in range(0, self.bad_http_connection_retries):
            try:
                func = getattr(bitcoind, name)
                result = func(*args, **kwargs)
                return result
            except ValueError as e:
                raise BitcoindJSONError("Probably could not authenticate against bitcoind-like RPC, try manually with curl") from e
            except socket.timeout as e:
                raise BitcoindJSONError("Got timeout when doing bitcoin RPC call {}. Maybe bitcoind was not synced with network?".format(name)) from e
            except CannotSendRequest as e:
                # AuthServiceProxy is unreliable and may up stuck in a state it cannot function anymore.
                # Thus, we recreate it.
                logger.error("Recoverable JSON-RPC API exception - most likely HTTP client stuck in a bad state. Will reconnect, reconnect attempt %d", retry)
                logger.exception(e)
                self.connect(reconnect=True)
                continue
            except (BadStatusLine, ConnectionRefusedError) as e:
                # This is the exception with SSH forwarding if the bitcoind is dead/stuck?

                # Clean up HTTP client, as otherwise the persistent connection will get stuck
                #   File "/Users/mikko/code/cryptoassets/cryptoassets/cryptoassets/core/backend/bitcoind.py", line 78, in api_call
                #     result = func(*args, **kwargs)
                #   File "/Users/mikko/code/applebytestore/venv/src/python-bitcoinrpc/bitcoinrpc/authproxy.py", line 125, in __call__
                #     'Content-type': 'application/json'})
                #   File "/Library/Frameworks/Python.framework/Versions/3.4/lib/python3.4/http/client.py", line 1090, in request
                #     self._send_request(method, url, body, headers)
                #   File "/Library/Frameworks/Python.framework/Versions/3.4/lib/python3.4/http/client.py", line 1118, in _send_request
                #     self.putrequest(method, url, **skips)
                #   File "/Library/Frameworks/Python.framework/Versions/3.4/lib/python3.4/http/client.py", line 966, in putrequest
                #     raise CannotSendRequest(self.__state)
                # http.client.CannotSendRequest: Request-sent

                # After error AuthConnetionProxy is in an invalid state. Reset it.
                # This should be r
                self.connect(reconnect=True)
                raise
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

    def get_backend_balance(self, confirmations=3):
        """Get full available hot wallet balance on the backend.
        :return Decimal:
        """
        return self.api_call("getbalance", self.bitcoind_account_name, confirmations)

    def get_received_by_address(self, address, confirmations=None):
        """
        """
        if confirmations is None:
            confirmations = self.default_confirmations

        assert type(confirmations) == int
        result = self.api_call("getreceivedbyaddress", address, confirmations)

        return _convert_to_satoshi(result)

    def list_received_transactions(self, extra={}):
        """Iterate through all received transactions known by backend.

        """
        return ListReceivedTransactionsIterator(self, extra)

    def get_transaction(self, txid):
        """ """
        return self.api_call("gettransaction", txid)

    def send(self, recipients, label):
        """ Broadcast outgoing transaction.

        This is called by send/receive process.

        :param recipients: Dict of (address, internal amount)
        """
        amounts = {}
        for address, decimals in recipients.items():

            # TODO: float() is here due to how bitcoin RPC passes values
            # Make sure conversion doesn't kill us if we lose accuracy accidentally
            converted = float(self.to_external_amount(decimals))

            accu = Decimal("0.00000001")
            d = Decimal(converted).quantize(accu)
            assert d == decimals.quantize(accu)

            amounts[address] = converted
            #assert Decimal(amounts[address]) == self.to_external_amount(decimals), "Got {} and {}".format(amounts[address], decimals)

        txid = self.api_call("sendmany", self.bitcoind_account_name, amounts, self.bitcoind_send_input_confirmations, label)

        # 'amount': Decimal('0E-8'), 'timereceived': 1416583349, 'fee': Decimal('-0.00010000'), 'txid': 'bf0decbc5726e75afdf9768dbbf611ae6ba52e3b36dbd96aecb3de2728ef8ebb', 'details': [{'category': 'send', 'address': 'mhShYyZhFgAmLwjaKyN2hN3HVt78a3BrtP', 'account': 'cryptoassets', 'amount': Decimal('-0.00002100'), 'fee': Decimal('-0.00010000')}, {'category': 'receive', 'address': 'mhShYyZhFgAmLwjaKyN2hN3HVt78a3BrtP', 'account': 'cryptoassets', 'amount': Decimal('0.00002100')}], 'confirmations': 0, 'hex': '0100000001900524bfa2d0ac8a361900b54fb8eb09287c9e4585cb446e66914f0db81dd36f000000006a473044022064210bad81028559d110a71142b29ce38ff13c1d712aa200913e3300b91b9ff7022050acbf3393443796104f38dd349b5dce1a12bec7e64308c7ec9f491476e8b9cc0121026a3dead5584ed1afa7f754ce8cb027be91ef418d7ddd7085fd690ad8a8d2196effffffff021c276c00000000001976a9141e966ad7ac7570fbd1d9d977fc382a9565c6bd3188ac34080000000000001976a914152247f71eaf81783
        # 197e357907857aecdb44bcb88ac00000000', 'walletconflicts': [], 'time': 1416583349}
        fee = 0
        txdata = self.api_call("gettransaction", txid)
        for detail in txdata["details"]:
            if detail["category"] == "send":
                fee += -1 * self.to_internal_amount(detail["fee"])

        return txid, fee

    def scan_addresses(self, addresses):
        """Give all known transactions to list of addresses.

        :param addresses: List of address strings

        :yield: Tuples of (txid, address, amount, confirmations)
        """
        raise RuntimeError("bitcoind cannot list transactions per address")


class BadWalletNotify(Exception):
    pass


class ListReceivedTransactionsIterator(base.ListTransactionsIterator):

    def __init__(self, backend, extra):
        self.backend = backend
        self.start = 0
        self.batch_size = 100
        self.extra = extra

    def _get_data(self, txid):
        return self.backend.get_transaction(txid)

    def fetch_next_txids(self):
        """
        :return: List of next txids to iterate or empty list if iterating is done.
        """
        confirmations = self.extra.get("confirmations", 0)

        now = time.time()
        attemps = 4

        out = []

        while attemps:

            logger.debug("listtransactions attempts #%d %s %d-%d", attemps, self.backend.bitcoind_account_name, self.start, self.start + self.batch_size)

            try:
                result = self.backend.api_call("listtransactions", self.backend.bitcoind_account_name, self.batch_size, self.start)

                out = [(res["txid"], self._get_data(res["txid"])) for res in result if res["category"] == "receive"]

                self.start += self.batch_size
                return out
            except KeyboardInterrupt:
                raise
            except:
                # http://bitcoin.stackexchange.com/questions/32839/bitcoind-json-rpc-interface-timeouts-under-unit-tests
                logger.error("listtransactions timeout failure after %f seconds", time.time() - now)
                attemps -= 1
                if attemps:
                    # Recreate connection. We are
                    self.bitcoind.connect(reconnect=True)
                    continue
                else:
                    raise
        return out
