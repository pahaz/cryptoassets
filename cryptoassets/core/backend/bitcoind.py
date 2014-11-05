"""bitcoind and bitcoind-likes backend.

Created upon https://github.com/4tar/python-bitcoinrpc/tree/p34-compatablity

"""

from bitcoinrpc.authproxy import AuthServiceProxy
from bitcoinrpc.authproxy import JSONRPCException

from .base import CoinBackend


class BitcoindJSONError(Exception):
    pass


class BitcoindDerivate(CoinBackend):
    """ Bitcoind or another altcoin using bitcoind-like JSON-RPC. """


class Bitcoind(BitcoindDerivate):
    """Backend for the original bitcoind (BTC) itself."""

    def __init__(self, url):
        self.url = url
        self.bitcoind = AuthServiceProxy(url)

    def api_call(self, name, *args, **kwargs):
        """ """
        try:
            func = getattr(self.bitcoind, name)
            return func(*args, **kwargs)
        except JSONRPCException as e:
            msg = e.error.get("message")
            if msg:
                raise BitcoindJSONError("Error communication with bitcoind API {}: {}".format(name, msg)) from e

    def import_private_key(self, label, key):
        result = self.api_call("getinfo")
        import ipdb; ipdb.set_trace()
        result = self.api_call("importprivkey", key, label, False)


    def create_address(self, label):
        """ Create a new receiving address.
        """
        raise NotImplementedError()

    def get_balances(self, addresses):
        """ Get balances on multiple addresses.
        """
        raise NotImplementedError()

    def get_lock(self, name):
        """ Create a named lock to protect the operation. """
        raise NotImplementedError()

    def send(self, recipients):
        """ Broadcast outgoing transaction.

        This is called by send/receive process.

        :param recipients: Dict of (address, internal amount)
        """
        raise NotImplementedError()
