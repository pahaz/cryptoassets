""" Block.Io API backend.

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
import pusherclient
from slugify import slugify

from block_io import BlockIo as _BlockIo


logger = logging.getLogger(__name__)


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

    def __init__(self, coin, api_key, pin, lock_factory):
        """
        """
        self.coin = coin
        self.block_io = _BlockIo(api_key, pin, 2)
        self.lock_factory = lock_factory
        self.monitor = None

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

    def scan_addresses(self, monitor, wallet, addresses):
        """ Update the internal address status to match ones in the blockchain.

        Call this within a db transaction block.

        :param monitor: SochainMonitor instance

        :param wallet: Wallet instance

        :param addresses: List of address strings
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
                tx = wallet.receive(txdata["txid"], address, amount, extra=dict(confirmations=txdata["confirmations"]))
                logger.debug("Updated incoming balance on tx {}, txid {}, address {}, to {}, tx confirmations {}".format(tx.id, tx.txid, address, amount, txdata["confirmations"]))

                # The transaction has become confirmed, no need to receive updates on it anymore
                if tx.credited_at:
                    monitor.finish_transaction(wallet.id, tx.txid)


class SochainPusher(pusherclient.Pusher):
    host = "slanger1.chain.so"

    def _connect_handler(self, data):
        # Some bug workdaround, tries to decode
        # JSON twices on initial on connected
        if type(data) == str:
            parsed = json.loads(data)
        else:
            parsed = data

        self.socket_id = parsed['socket_id']

        self.state = "connected"


class SochainTransctionThread(threading.Thread):
    """ A background thread getting updates on hot transactions. """

    def __init__(self, block_io, monitor):
        self.alive = True
        self.block_io = block_io
        self.monitor = monitor
        threading.Thread.__init__(self)
        self.daemon = True

    def run(self):

        from cryptoassets.core.models import DBSession
        session = DBSession

        while self.alive:
            for wallet_id, data in self.monitor.wallets.items():

                with transaction.manager:

                    Wallet = self.monitor.wallets[wallet_id]["klass"]
                    wallet = session.query(Wallet).filter_by(id=wallet_id).first()
                    assert wallet is not None, "Could not load a specific wallet {}".format(wallet_id)

                    addresses = [address for txid, address in self.monitor.wallets[wallet_id]["transactions"].items()]
                    self.block_io.scan_addresses(self.monitor, wallet, addresses)

            time.sleep(5)

    def stop(self):
        self.alive = False


class SochainMonitor:
    """ A primitive incoming transaction monitor using chain.so service.

    Subscribe to address status on chain.so using Pusher service.
    When there is an incoming transaction, extract the transaction id from pusher data
    and then use the actual block.io service to ask the status of this address (we don't
    trust Pusher data alone, as bitcoind nodes might be out of sync).
    """

    def __init__(self, block_io, wallets, pusher_app_key, network):
        """

        https://chain.so/api#networks-supported

        :param wallets: Initial wallet object list to Monitor

        :param network: SoChain network id e.g. BTCTEST
        """

        assert isinstance(block_io, BlockIo)
        assert hasattr(wallets, '__iter__'), "Take a list of wallets, not a single wallet"
        assert network in ("btc", "btctest", "doge", "dogetest")

        # Monitored wallets list
        # wallet id -> {lastid, addresses}
        self.wallets = {}
        self.period_seconds = 0.2

        self.network = network
        self.connected = False
        self.block_io = block_io
        self.init_pusher(pusher_app_key, wallets)

        self.transaction_thread = SochainTransctionThread(block_io, self)

    def init_pusher(self, pusher_app_key, wallets):
        """
        """

        # Inherit logging level from this module
        self.pusher = SochainPusher(pusher_app_key, log_level=logger.level)

        def connected(data):
            self.connected = True
            self.transaction_thread.start()
            for wallet in wallets:
                self.include_wallet(wallet)

        self.pusher.connection.bind('pusher:connection_established', connected)
        self.pusher.connect()

    def close(self):
        """
        """
        if self.connected:
            self.pusher.disconnect()
            self.transaction_thread.stop()
            self.connected = False

    def include_wallet(self, wallet):
        """ Add a wallet on the monitoring list.
        """
        assert wallet.id

        # Put this wallet on the monitoring list

        # Assume we are in Pusher client thread,
        # we need to create a new database session and
        # we cannot recycle any objects
        self.wallets[wallet.id] = dict(last_id=-1, addresses=set(), transactions={}, klass=wallet.__class__)
        self.include_addresses(wallet.id)

    def include_addresses(self, wallet_id):
        """ Include all the wallets receiving addresses on the monitored list.

        XXX: Transaction scoping
        """

        from cryptoassets.core.models import DBSession
        session = DBSession

        assert wallet_id
        assert type(wallet_id) == int
        last_id = self.wallets[wallet_id]["last_id"]
        Wallet = self.wallets[wallet_id]["klass"]

        assert session.query(Wallet).count() > 0, "No wallets visible in Sochain monitor. Multithreading issue?".format(wallet_id)

        wallet = session.query(Wallet).filter_by(id=wallet_id).first()
        assert wallet is not None, "Could not load a specific wallet {}".format(wallet_id)

        addresses = wallet.get_receiving_addresses()
        assert addresses.count() > 0

        for address in addresses.filter(wallet.Address.id > last_id, wallet.Address.archived_at is not None):  # noqa
            assert address.address not in self.wallets[wallet.id]["addresses"], "Tried to double monitor address {}".format(address.address)
            self.wallets[wallet.id]["addresses"].add(address.address)
            self.wallets[wallet.id]["last_id"] = address.id
            self.subscribe_to_address(address.address)

    def include_transactions(self, wallet_id):
        """ Include all the wallet unconfirmed transactions on the monitored list. """
        from cryptoassets.core.models import DBSession
        session = DBSession

        assert wallet_id
        assert type(wallet_id) == int
        Wallet = self.wallets[wallet_id]["klass"]

        wallet = session.query(Wallet).filter_by(id=wallet_id).first()
        assert wallet is not None, "Could not load a specific wallet {}".format(wallet_id)

        # Start subscribing to transactions still unfinished
        unconfirmed_txs = wallet.get_active_external_received_transcations()
        for tx in unconfirmed_txs:
            self.subscribe_to_transaction(tx.address, tx.txid)

    def finish_transaction(self, wallet_id, txid):
        if txid in self.wallets[wallet_id]["transactions"]:
            del self.wallets[wallet_id]["transactions"][txid]

    def subscribe_to_address(self, address):
        """ Make a Pusher subscription for incoming transactions

        https://chain.so/api#realtime-balance-updates

        https://github.com/ekulyk/PythonPusherClient

        :param wallet: The source wallet of this addresss

        :param address: Address as a string
        """
        logger.debug("Subscribed to new address {}".format(address))
        pusher_channel = "address_{}_{}".format(self.network, address)
        channel = self.pusher.subscribe(pusher_channel)
        channel.bind('balance_update', self.on_balance_updated)

    def subscribe_to_transaction(self, wallet_id, address, txid):
        """ Subscribe to get updates of a transaction.
        """
        # logger.info("Subscribed to new transaction {}".format(txid))
        # pusher_channel = "confirm_tx_{}_{}".format(self.network, txid)
        # channel = self.pusher.subscribe(pusher_channel)
        # channel.bind('balance_update', self.on_confirm_transaction)
        wallet_data = self.wallets[wallet_id]
        wallet_data["transactions"][txid] = address

    def on_balance_updated(self, data):
        """ chain.so tells us there should be a new transaction.

        Query block.io for authotarive transcation information.
        """

        # {"type": "address",
        # "value": {"value_sent": "-0.00888400", "value_received": "0.00885300", "balance_change": "-0.00003100",
        # "tx": {"inputs":
        # [{"script": "x", "input_no": 0, "value": "0.00888400", "address": "2MsgW3kCrRFtJuo9JNjkorWXaZSvLk4EWRr", "type": "scripthash", "from_output": {"output_no": 1, "txid": "e8e2d9384a33b05104a1d713505976a4153212ff005a5243de2cd1798376b1de"}}], "outputs": [{"script": "OP_HASH160 6dbb09b6f80fc8114fc03f51f917b999133e3c4c OP_EQUAL", "type": "scripthash", "value": "0.00002100", "output_no": 0, "address": "2N3FRhpPnDh6TinUJxiLaeofaYFfGLmRCgG"},
        # {"script": "x", "type": "scripthash", "value": "0.00885300", "output_no": 1, "address": "x"}], "txid": "x"}, "address": "x"}}
        data = json.loads(data)
        address = data["value"]["address"]

        # We are in the monitor thread,
        # create new DB session
        from cryptoassets.core.models import DBSession
        session = DBSession

        # Find the wallet we received a notification about
        for wallet_id, wallet_data in self.wallets.items():
            addresses = wallet_data["addresses"]
            if address in addresses:
                Wallet = wallet_data["klass"]
                break
        else:
            logger.error("Received on_balance_update() on unknown wallet, address {}".format(address))
            return

        # We want notifications when the confirmation state changes
        self.subscribe_to_transaction(wallet_id, address, data["value"]["tx"]["txid"])

        with transaction.manager:

            # Load related wallet
            wallet = session.query(Wallet).filter_by(id=wallet_id).first()
            assert wallet

            self.block_io.scan_addresses(self, wallet, [address])

    def refresh_addresses(self):
        """
        """
        self.include_addresses(self.last_id)


