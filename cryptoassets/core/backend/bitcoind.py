"""bitcoind and bitcoind-likes backend.

Created upon https://github.com/4tar/python-bitcoinrpc/tree/p34-compatablity

"""

from bitcoinrpc.authproxy import AuthServiceProxy
from bitcoinrpc.authproxy import JSONRPCException

from .base import CoinBackend


def _address_from_private_key(private_key):
    """ """
    secret_exponent = int(binascii.hexlify(b58check_decode(private_key)), 16)
    ecdsa_private_key = ecdsa.keys.SigningKey.from_secret_exponent(secret_exponent, self._curve, self._hash_function)
    ecdsa_public_key = ecdsa_private_key.get_verifying_key()
    return b58check_encode(self._bin_hash160(), version_byte=self.version_byte('pubkey_hash'))


def _convert_to_satoshi(amount):
    """ BlockIO reports balances as decimals. Our database represents them as satoshi integers. """
    d = Decimal(amount)
    d2 = d * Decimal("100000000")
    # Safety check
    assert is_integer(d2)
    return int(d2)


def _convert_to_decimal(satoshis):
    """ BlockIO reports balances as decimals. Our database represents them as satoshi integers. """
    d = Decimal(satoshis)
    d2 = d / Decimal("100000000")
    return str(d2.quantize(Decimal("0.00000001")))


class BitcoindJSONError(Exception):
    pass


class BitcoindDerivate(CoinBackend):
    """ Bitcoind or another altcoin using bitcoind-like JSON-RPC. """


class Bitcoind(BitcoindDerivate):
    """Backend for the original bitcoind (BTC) itself."""

    def __init__(self, coin, url):
        """
        :param coin: Threel letter coin acronym
        :param url: bitcoind connection url
        """
        self.url = url
        self.bitcoind = AuthServiceProxy(url)
        self.coin = coin
        self.default_confirmations = 3

    def api_call(self, name, *args, **kwargs):
        """ """
        try:
            func = getattr(self.bitcoind, name)
            result = func(*args, **kwargs)
            return result
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
        raise NotImplementedError()

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
        result = self.api_call("listtransactions", "", start, limit)
        ipdb
        return result

    def get_lock(self, name):
        """ Create a named lock to protect the operation. """
        raise NotImplementedError()

    def send(self, recipients):
        """ Broadcast outgoing transaction.

        This is called by send/receive process.

        :param recipients: Dict of (address, internal amount)
        """
        raise NotImplementedError()

    def monitor_address(self, address):
        """Bitcoind incoming transactions on address monitoring.

        ATM does nothing as this needs to be set up in bitcoind config file.
        """

