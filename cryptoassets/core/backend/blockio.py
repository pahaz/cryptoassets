"""Block.Io API backend.

Supports Bitcoin, Dogecoin and Litecoin on `block.io <https://block.io>`_ API.

For incoming transactions it uses `SoChain <https://chain.so>`_ service.

For the usage instructions see :py:mod:`cryptoassets.tests.test_block_io`.
"""

import json
import threading
import time
import logging
from collections import Counter
from decimal import Decimal

import transaction
from slugify import slugify

from block_io import BlockIo as _BlockIo

from .base import CoinBackend

logger = logging.getLogger(__name__)


class BlockIo(CoinBackend):
    """Block.io API."""

    def __init__(self, coin, api_key, pin, walletnotify=None):
        """
        :param wallet_notify: Wallet notify configuration
        """
        self.coin = coin
        self.block_io = _BlockIo(api_key, pin, 2)
        # self.lock_factory = lock_factory
        self.monitor = None

        self.walletnotify_config = walletnotify

    def to_internal_amount(self, amount):
        return Decimal(amount)

    def to_external_amount(self, amount):
        return Decimal(amount)

    def create_address(self, label):

        # # block.io does not allow arbitrary characters in labels
        label = slugify(label)
        result = self.block_io.get_new_address(label=label)
        # {'data': {'address': '2N2Qqvj5rXv27rS6b7rMejUvapwvRQ1ahUq', 'user_id': 5, 'label': 'slange11', 'network': 'BTCTEST'}, 'status': 'success'}

        address = result["data"]["address"]

        return address

    def monitor_address(self, address):
        """ Add address object to the receiving transaction monitoring list.

        :param address: address object
        """
        assert address.account
        assert address.address
        if self.monitor:
            self.monitor.subscribe_to_address(address.address)

    def monitor_transaction(self, transaction):
        """ Add a transaction id on the receiving transaction monitoring list.
        """
        assert transaction.id
        assert transaction.txid
        if self.monitor:
            self.monitor.subscribe_to_transaction(transaction.txid)

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

    def get_backend_balance(self, confirmations=3):
        """Get full available hot wallet balance on the backend.
        :return Decimal:
        """

        resp = self.block_io.get_balance()
        # {'status': 'success', 'data': {'pending_received_balance': '0.00000000', 'available_balance': '0.13553300', 'network': 'BTCTEST'}}
        if confirmations == 0:
            return self.to_internal_amount(resp["data"]["pending_received_balance"])
        else:
            return self.to_internal_amount(resp["data"]["available_balance"])

    def get_lock(self, name):
        """ Create a named lock to protect the operation. """
        return self.lock_factory(name)

    def send(self, recipients, label):
        """
        BlockIo does not support labelling outgoing transactions.

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

    def scan_addresses(self, addresses):
        """Give all known transactions to list of addresses.

        :param addresses: List of address strings

        :yield: Tuples of (txid, address, amount, confirmations)
        """

        # List type
        assert hasattr(addresses, '__iter__'), "Take a list of addresses, not a single address"

        resp = self.block_io.get_transactions(type="received", addresses=",".join(addresses))

        for txdata in resp["data"]["txs"]:

            # Each transaction can have the same input/output several times
            # sum them up
            received = Counter()
            for entry in txdata["amounts_received"]:
                address = entry["recipient"]
                amount = self.to_internal_amount(entry["amount"])
                received[address] += amount

            assert amount > 0, "Could not parse amount from {}".format(txdata)

            for address, amount in received.items():
                # wallet.receive() will get wallet and account lock for us
                yield txdata["txid"], address, amount, txdata["confirmations"]

