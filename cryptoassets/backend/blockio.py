"""
    Block.Io wallet implementation.

    - All transactions are asynchronouos

    - Local cached data is kept on the server-side

"""

import threading
import time
from decimal import Decimal

import pusherclient
from slugify import slugify

from block_io import BlockIo as _BlockIo
from .base import Monitor


def is_integer(d):
    """ Check if Decimal instance has fractional part. """
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

    def __init__(self, coin, api_key, pin, lock_factory, monitor=None):
        """
        """
        self.coin = coin
        self.block_io = _BlockIo(api_key, pin, 2)
        self.lock_factory = lock_factory

        if not monitor:
            monitor = ThreadMonitor()

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

    def get_receiver(self):
        """ Return the backend receiving transactions monitor. """
        return Monitor()

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

    def start_incoming_monitoring(self, addresses):
        """ Begin monitor the incoming transactions.
        """
        self.monitor = Monitor()

    def refresh_address_incoming_transactions(self, address):
        """ Ask the backend for the status of address incoming transactions.
        """

    def stop_incoming_monitoring(self):
        """ Monitor the incoming
        """


class SochainMonitor:
    """ Very primitive incoming transaction monitor using chain.so service. initial='

    Subscribe to address status on chain.so using Pusher service.
    When there is an incoming transaction, extract the transaction id from pusher data
    and then use the actual block.io service to ask the status of this address (we don't
    trust Pusher data alone, as bitcoind nodes might be out of sync).
    """

    def __init__(self, wallet, pusher_app_key):
        """
        """
        self.last_id = -1
        self.running = False
        self.wallet = wallet
        self.period_seconds = 0.2

        #: List of address strings
        self.monitored_addresses = []

        self.connected = False
        self.init_pusher(pusher_app_key)

    def init_pusher(self, pusher_app_key):
        """
        """
        self.pusher = pusherclient.Pusher(pusher_app_key)
        self.pusher.connection.bind('pusher:connection_established', self.on_connected)
        self.pusher.connect()

    def close(self):
        """
        """
        if self.connected:
            self.pusher.disconnect()
            self.connected = False

    def on_connected(self):
        self.connected = True
        self.include_addresses(self.last_id)

    def subscribe_to_address(self, address):
        """
        :param address: Address as a string
        """
        pusher_channel = "address_{}_{}".format(self.wallet.coin, address)
        channel = self.pusher.subscribe(pusher_channel)
        channel.bind('balance_update', self.on_balance_updated)

    def on_balance_updated(self, data):
        """ chain.so tells us there should be a new transaction. """
        print("Balance update {}".format(data))

    def include_addresses(self, last_id):
        """ Include new receiving addresses on the monitored list.

        https://chain.so/api#realtime-balance-updates

        https://github.com/ekulyk/PythonPusherClient
        """

        for address in self.wallet.get_receiving_addresses().filter_by(self.wallet.Address.id > self.last_id, self.wallet.Address.archived_at != None):  # noqa
            assert address.address not in self.addresses
            self.addresses.append(address.address)
            self.last_id = address.id
            self.subscribe_to_address(address.address)

    def refresh_addresses(self):
        """
        """
        self.include_addresses(self.last_id)
