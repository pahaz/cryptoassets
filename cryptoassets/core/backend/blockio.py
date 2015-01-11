"""Block.Io API backend.

Supports Bitcoin, Dogecoin and Litecoin on `block.io <https://block.io>`_ API.

The backend configuration takes following parameters.

:param class: Always ``cryptoassets.core.backend.blockio.BlockIo``

:param api_key: block.io API key

:param password: block.io password

:param network: one of ``btc``, ``btctest``, ``doge``, ``dogetest``, see `chain.so <https://chain.so>`_ for full list

You must use :py:mod:`cryptoassets.core.backend.sochainwalletnotify` as ``walletnotify`` for incoming transactions for now.
"""


import logging
from decimal import Decimal
import datetime

import requests
from slugify import slugify

from block_io import BlockIo as _BlockIo

from . import base


logger = logging.getLogger(__name__)


def _transform_txdata_to_bitcoind_format(inp):
    """Grab out data as mangle we expect it to be.

    Input chain.so format txdata and output it as bitcoind format txdata. We probably miss half of the things ATM, so please keep updating this function.
    """
    output = {}
    assert inp["status"] == "success"
    inp = inp["data"]
    output["confirmations"] = inp["confirmations"]
    output["txid"] = inp["txid"]
    output["details"] = []

    for op in inp["outputs"]:
        output["details"].append(dict(category="receive", address=op["address"], amount=Decimal(op["value"])))

    output["only_receive"] = True

    return output


class BlockIo(base.CoinBackend):
    """Block.io API."""

    def __init__(self, coin, api_key, pin, network=None, walletnotify=None):
        """
        :param wallet_notify: Wallet notify configuration
        """

        base.CoinBackend.__init__(self)

        self.coin = coin
        self.block_io = _BlockIo(api_key, pin, 2)

        assert network, "Please give argument network as one of chain.so networks: btc, btctest, doge, dogetest"

        self.network = network

        self.walletnotify_config = walletnotify

    def require_tracking_incoming_confirmations(self):
        return True

    def to_internal_amount(self, amount):
        return Decimal(amount)

    def to_external_amount(self, amount):
        return str(amount)

    def create_address(self, label):

        # # block.io does not allow arbitrary characters in labels
        label = slugify(label)
        result = self.block_io.get_new_address(label=label)
        # {'data': {'address': '2N2Qqvj5rXv27rS6b7rMejUvapwvRQ1ahUq', 'user_id': 5, 'label': 'slange11', 'network': 'BTCTEST'}, 'status': 'success'}

        address = result["data"]["address"]

        return address

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

    def get_transaction(self, txid):
        """ """
        resp = requests.get("https://chain.so//api/v2/get_tx/{}/{}".format(self.network, txid))
        data = resp.json()
        data = _transform_txdata_to_bitcoind_format(data)
        return data

    def list_received_transactions(self, extra={}):
        """ """
        return ListReceivedTransactionsIterator(self)


class ListReceivedTransactionsIterator(base.ListTransactionsIterator):
    """Receive a batch of receive transactiosn from block.io API.

    https://block.io/api/simple/python
    """
    def __init__(self, backend):
        self.backend = backend
        self.before_tx = None
        self.last_timestamp = None

    def fetch_next_txids(self):
        """
        :return: List of next txids to iterate or empty list if iterating is done.
        """

        # block.io bug with before_tx
        return []

        logger.info("Asking block.io for new received transaction batch, before_tx %s (%s)", self.before_tx, datetime.datetime.fromtimestamp(self.last_timestamp) if self.last_timestamp else "-")

        if self.before_tx:
            result = self.backend.block_io.get_transactions(type="received", before_tx=self.before_tx)
        else:
            result = self.backend.block_io.get_transactions(type="received")

        txs = result["data"]["txs"]

        # Confirmed oldest timestamp is the last
        for tx in txs:
            logger.debug("Tx txid:%s timestamp %s", tx["txid"], datetime.datetime.fromtimestamp(tx["time"]))

        if txs:
            # The last txid to keep us iterating
            self.before_tx = txs[-1]["txid"]
            self.last_timestamp = txs[-1]["time"]

        return [tx["txid"] for tx in txs]
