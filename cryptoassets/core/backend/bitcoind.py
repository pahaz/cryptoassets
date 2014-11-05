"""bitcoind and bitcoind-likes backend.


"""

from .base import CoinBackend


class BitcoindDerivate(CoinBackend):
    """ Bitcoind or another altcoin using bitcoind-like JSON-RPC. """


class Bitcoind(BitcoindDerivate):
    """Backend for the original bitcoind (BTC) itself."""

    def __init__(self, url):
        self.url = url
        self.bitcoind_api = None

    def import_private_key(self, label, key):
        self.bitcoind.importprivkey(key, label)

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
