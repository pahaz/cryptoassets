"""Block.Io API backend.

Supports Bitcoin, Dogecoin and Litecoin on `block.io <https://block.io>`_ API.

The backend configuration takes following parameters.

:param class: Always ``cryptoassets.core.backend.blockio.BlockIo``

:param api_key: block.io API key

:param password: block.io password

:param network: one of ``btc``, ``btctest``, ``doge``, ``dogetest``, see `chain.so <https://chain.so>`_ for full list

:param walletnotify: Configuration of wallet notify service set up for incoming transactions. You must use :py:class:`cryptoassets.core.backend.blockiowebhook.BlockIoWebhookNotifyHandler` or :py:class:`cryptoassets.core.backend.blockiowebocket.BlockIoWebsocketNotifyHandler` as ``walletnotify`` for incoming transactions for now. See below for more details.

Example configuration for block.io backend using websockets.

.. code-block:: yaml

    ---
    # Cryptoassets.core configuration for running block.io unit tests

    database:
      url: sqlite:////tmp/cryptoassts-unittest-blockio.sqlite

    coins:
        doge:
            backend:
                class: cryptoassets.core.backend.blockio.BlockIo
                api_key: yyy
                pin: xxxx
                network: dogetest
                walletnotify:
                    class: cryptoassets.core.backend.blockiowebsocket.BlockIoWebsocketNotifyHandler

    """


import logging
from decimal import Decimal
import datetime
import threading

import requests
from slugify import slugify

from block_io import BlockIo as _BlockIo

from . import base
from ..utils import iterutil

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
        self.api_key = api_key
        self.pin = pin
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
        """Create a new address on block.io wallet.

        Note that block.io blocks creating addresses with the same label.
        """
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
        resp = requests.get("https://chain.so/api/v2/get_tx/{}/{}".format(self.network, txid))
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
        self.finished = False

    def _format_bitcoind_like(self, result):
        """Grab data from block.io response and format received details bitcoind like.

        https://block.io/api/v2/get_transactions/?api_key=923f-e3e9-a580-dfb2&type=received
        """
        out = {}
        out["confirmations"] = result["confirmations"]
        out["txid"] = result["txid"]

        details = []
        for received in result["amounts_received"]:
            details.append(dict(category="receive", address=received["recipient"], amount=Decimal(received["amount"])))

        # See top comment
        out["only_receive"] = True

        out["details"] = details
        return out

    def fetch_next_txids(self):
        """
        :return: List of next txids to iterate or empty list if iterating is done.
        """

        if self.finished:
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

            # workaround
            # <moo-_-> kindoge: there is still subtle bug in the last bug fix
            # <moo-_-> https://block.io/api/v2/get_transactions/?api_key=0266-c2b6-c2c8-ee07&type=received&before_tx=d30a7d054c11718a6ce9ca6c9a5a95575e8cc7fb27f38f4427a65a02df4ba427
            if self.before_tx == txs[-1]["txid"]:
                self.finished = True

            # The last txid to keep us iterating
            self.before_tx = txs[-1]["txid"]
            self.last_timestamp = txs[-1]["time"]

        return [(tx["txid"], self._format_bitcoind_like(tx)) for tx in txs]


def clean_blockio_test_wallet(backend, balance_threshold=Decimal(1)):
    """Go through unused test addresses and archives them on block.io.

    block.io has limit of 2000 active addresses on free plan. If you exceed the limit and do not archive your addresses, block.io stops doing withdrawals.

    This helper function walks through a testnet wallet we use for unit tests and figures out which addresses look like test addresses, then consolidates them together.

    :param balance_threshold: How low the address balance must be before we consolidate it together to one big balance address.
    """

    block_io = backend.block_io

    needs_archive = []

    # Move all test transfers under this address
    consolidation_address = None

    result = block_io.get_my_addresses()
    addresses = result["data"]["addresses"]
    network = result["data"]["network"]

    # block.io has an issue that you cannot withdrawal under certain threshold from address
    # 2015-02
    network_withdrawal_limits = {
        "DOGETEST": Decimal(2)
    }

    network_fees = {
        "DOGETEST": Decimal(1),
        "BTCTEST": Decimal(1000) / Decimal(10 ** 8)
    }

    withdrawal_limit = network_withdrawal_limits.get(network, 0)

    network_fee = network_fees.get(network, 0)

    result = block_io.get_my_archived_addresses()
    archived_addresses = [entry["address"] for entry in result["data"]["addresses"]]

    for addr in addresses:

        if addr["label"] == "default":
            # block.io: Exception: Failed: Cannot archive addresses with label=default.
            continue

        # {'available_balance': '0.00000000', 'address': '2MvB2nKMKcWakVJxB3ZhPnG9eqWsEoX4CBD', 'user_id': 1, 'label': 'test-address-1413839537-401918', 'pending_received_balance': '0.00000000'}
        balance = Decimal(addr["available_balance"]) + Decimal(addr["pending_received_balance"])
        if balance == 0:
            needs_archive.append(addr["address"])
            continue

        if balance < balance_threshold:
            if not consolidation_address:
                # Use the first found low balance address as the consolidation destionation
                consolidation_address = addr["address"]
            else:

                if balance - network_fee < withdrawal_limit:
                    logger.info("Cannot consolidate %s from %s, too low balance for block.io API call", balance, addr["address"])
                else:
                    # Move everyhing from this address to the consolidation address
                    logger.info("Consolidating %s from %s to %s", balance, addr["address"], consolidation_address)

                    block_io.withdraw_from_addresses(amounts=str(balance - network_fee), from_addresses=addr["address"], to_addresses=consolidation_address)

            needs_archive.append(addr["address"])

    not_yet_archived = set(needs_archive) - set(archived_addresses)

    logger.info("Archiving %d addresses from total %s, already archived %d, not yet archived %d", len(needs_archive), len(addresses), len(archived_addresses), len(not_yet_archived))

    # block.io seems to have an upper limit how many addresses you can arcihive at once
    for chunk in iterutil.grouper(256, not_yet_archived):
        logger.debug("Archiving chunk of %d addresses", len(chunk))
        result = block_io.archive_addresses(addresses=",".join(chunk))
        assert result["status"] == "success"
