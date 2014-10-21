"""
    Block.Io wallet implementation.

    - All transactions are asynchronouos

    - Local cached data is kept on the server-side

"""

from decimal import Decimal
from slugify import slugify

from block_io import BlockIo as _BlockIo


def is_integer(d):
    return d == d.to_integral_value()


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


class BlockIo:
    """ Synchronous block.io API. """

    def __init__(self, coin, api_key, pin, lock_factory):
        """
        """
        self.coin = coin
        self.block_io = _BlockIo(api_key, pin, 2)
        self.lock_factory = lock_factory

    def to_internal_amount(self, amount):
        if self.coin == "btc":
            return _convert_to_satoshi(amount)
        else:
            return int(Decimal(amount))

    def to_external_amount(self, amount):
        if self.coin == "btc":
            return _convert_to_decimal(amount)
        else:
            return int(amount)

    def create_address(self, label):
        """
        """

        # block.io does not allow arbitrary characters in labels
        # {'data': {'address': '2N2Qqvj5rXv27rS6b7rMejUvapwvRQ1ahUq', 'user_id': 5, 'label': 'slange11', 'network': 'BTCTEST'}, 'status': 'success'}
        label = slugify(label)
        result = self.block_io.get_new_address(label=label)
        assert result["status"] == "success"
        return result["data"]["address"]

    def get_balances(self, addresses):
        """ Get balances on multiple addresses.

        """
        result = self.block_io.get_address_balance(addresses=",".join(addresses))
        # {'data': {'balances': [{'pending_received_balance': '0.00000000', 'address': '2MsgW3kCrRFtJuo9JNjkorWXaZSvLk4EWRr',
        # 'available_balance': '0.42000000', 'user_id': 0, 'label': 'default'}], 'available_balance': '0.42000000',
        # 'network': 'BTCTEST', 'pending_received_balance': '0.00000000'}, 'status': 'success'}

        if "balances" not in result["data"]:
            # Not yet address on this wallet
            raise StopIteration

        for balance in result["data"]["balances"]:
            yield balance["address"], self.to_internal_amount(balance["available_balance"])

    def get_lock(self, name):
        """ Create a named lock to protect the operation. """
        return self.lock_factory(name)

    def send(self, recipients):
        """
        :param recipients: Dict of (address, satoshi amount)
        """

        assert recipients

        amounts = []
        addresses = []
        for address, satoshis in recipients.items():
            amounts.append(str(self.to_external_amount(satoshis)))
            addresses.append(address)

        resp = self.block_io.withdraw(amounts=",".join(amounts), to_addresses=",".join(addresses))

        return resp["data"]["txid"], self.to_internal_amount(resp["data"]["network_fee"])

    def receive(self, receiver, amount):
        """
        """
