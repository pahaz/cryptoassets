"""Coin models support pluggable address validators.

We provide some validators just to make sure we don't write bad outgoing transactions to our database.
"""

import abc
import logging
from hashlib import sha256

logger = logging.getLogger(__name__)


class AddressValidator(abc.ABC):
    """Define address validation interface.

    You should not call this directly, instead use :py:meth:`cryptoassets.core.coin.registry.Coin.validate_address`.

    """

    @abc.abstractmethod
    def validate_address(self, address, testnet):
        """
        :param address: Address as a string

        :param testnet: We are in testnet

        :return: True if the address is valid
        """


class NullAddressValidator(AddressValidator):

    def validate_address(self, address, testnet):
        return True


class HashAddresValidator(AddressValidator):
    """Check that hash in the address is good.

    Does not do extensive checks like address type, etc. one could do with pycoin.

    http://rosettacode.org/wiki/Bitcoin/address_validation
    """

    digits58 = '123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz'

    def decode_base58(self, bc, length):
        n = 0
        for char in bc:
            n = n * 58 + self.digits58.index(char)
        return n.to_bytes(length, 'big')

    def check_bc(self, bc):
        bcbytes = self.decode_base58(bc, 25)
        return bcbytes[-4:] == sha256(sha256(bcbytes[:-4]).digest()).digest()[:4]

    def validate_address(self, address, testnet):
        return self.check_bc(address)


class NetworkCodeAddressValidator(AddressValidator):
    """Check if Bitcoin style address is valid using pycoin library.

    XXX: Issues, could not get working.
    """

    def __init__(self, netcode, testnetcode):
        self.netcode = netcode
        self.testnetcode = testnetcode

    def validate_address(self, address, testnet):
        raise NotImplementedError()