"""bitcoind and bitcoind-likes backend.

Created upon https://github.com/4tar/python-bitcoinrpc/tree/p34-compatablity

Developer reference: https://bitcoin.org/en/developer-reference#bitcoin-core-apis

Original API call list: https://en.bitcoin.it/wiki/Original_Bitcoin_client/API_calls_list
"""

import logging
import transaction
import datetime
import socket
import time
from decimal import Decimal
from http.client import BadStatusLine
#from os import ConnectionRefusedError
from collections import Counter

from zope.dottedname.resolve import resolve

from bitcoinrpc.authproxy import AuthServiceProxy
from bitcoinrpc.authproxy import JSONRPCException

from .base import CoinBackend

from .pipewalletnotify import PipedWalletNotifyHandler
from .transactionupdater import TransactionUpdater

from ..coin.registry import Coin
from ..notify.registry import NotifierRegistry

logger = logging.getLogger(__name__)


TIMEOUT = 10


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
        self.bitcoind = AuthServiceProxy(url, timeout=TIMEOUT)
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
            self.bitcoind = AuthServiceProxy(self.url, timeout=TIMEOUT)
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

    def list_transactions(self, start, limit):
        """
        """

        # http://bitcoin.stackexchange.com/questions/32839/bitcoind-json-rpc-interface-timeouts-under-unit-tests
        now = time.time()
        attemps = 4
        while attemps:

            logger.info("listtransactions attempts #%d %s %s %s", attemps, self.bitcoind_account_name, limit, start)
            try:
                result = self.api_call("listtransactions", self.bitcoind_account_name, limit, start)
                return result
            except:
                logger.error("listtransactions timeout failure after %f seconds", time.time() - now)
                attemps -= 1
                if attemps:
                    # Recreate connection
                    self.bitcoind = AuthServiceProxy(self.url)
                    continue
                else:
                    raise

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

    def scan_addresses(self, addresses):
        """Give all known transactions to list of addresses.

        :param addresses: List of address strings

        :yield: Tuples of (txid, address, amount, confirmations)
        """
        raise RuntimeError("bitcoind cannot list transactions per address")

    def create_transaction_updater(self, session, notifiers):
        tx_updater = TransactionUpdater(session, self, self.coin, notifiers)
        return tx_updater


class BadWalletNotify(Exception):
    pass


