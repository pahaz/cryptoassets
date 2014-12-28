"""Handle incoming transaction notifications using chain.so service."""

import json
import logging
import threading
import time
from decimal import Decimal

import pusherclient

from .base import IncomingTransactionRunnable


logger = logging.getLogger(__name__)


class SochainConnection(pusherclient.Connection):
    """Bugfixed pusherclient"""
    def _connect_handler(self, data):
        # Some bug workdaround, tries to decode
        # JSON twices on initial on connected
        if type(data) == str:
            parsed = json.loads(data)
        else:
            parsed = data

        self.socket_id = parsed['socket_id']

        self.state = "connected"


class SochainPusher(pusherclient.Pusher):
    host = "slanger1.chain.so"

    def __init__(self, key, secure=True, secret=None, user_data=None, log_level=logging.INFO, daemon=True):
        self.key = key
        self.secret = secret
        self.user_data = user_data or {}

        self.channels = {}

        self.connection = SochainConnection(self._connection_handler, self._build_url(key, secure), log_level=log_level, daemon=daemon)


class SochainTransctionThread(threading.Thread):
    """A background thread getting updates on hot transactions.

    Maintain a list of open transaction where confirmation threshold is less than our confirmation level. Then, in a poll loop check those transactions until we are done with them. We need to do this unti Sochain gets an Pusher notifications for confirmation updates.
    """

    def __init__(self, monitor):
        self.alive = True
        self.monitor = monitor
        self.poll_period = 5
        threading.Thread.__init__(self)

    def run(self):
        while self.alive:
            addresses = self.monitor.transactions.values()
            self.rescan_addresses(addresses)
            time.sleep(self.poll_period)

    def rescan_addresses(self, addresses):
        """Scan all addresses where we know we have pending incoming transactions."""

        addresses = []
        for txid, address, amount, confirmations in self.monitor.transaction_updater.backend.scan_addresses(addresses):
            txid, credited = self.monitor.transaction_updater.handle_address_receive(txid, address, amount, confirmations)

            # Don't poll transaction anymore if it's finished
            if credited:
                self.monitor.finish_transaction(txid)

    def stop(self):
        self.alive = False


class SochainWalletNotifyHandler(threading.Thread, IncomingTransactionRunnable):
    """Detect and monitor incoming transactions using chain.so service.

    Open a websocket connection to read updates for transactions.
    """

    def __init__(self, pusher_app_key, transaction_updater, network, poll_period=0.2):
        """Configure a HTTP wallet notify handler server.

        :param transaction_updater: Instance of :py:class:`cryptoassets.core.backend.bitcoind.TransactionUpdater` or None

        :param network: Sochain Network id as a string "btctest"
        """
        threading.Thread.__init__(self)
        self.transaction_updater = transaction_updater
        self.pusher_app_key = pusher_app_key
        self.running = False
        self.network = network
        self.transaction_thread = None
        self.poll_period = float(poll_period)
        #: Wallet id -> wallet data mapping
        #: dict(last_id=-1, addresses=set(), klass=wallet.__class__)
        self.wallets = {}
        self.transactions = {}

    def init_monitoring(self, pusher_app_key, network):
        """Create and run threads we need to keep Sochain monitoring kicking.

        https://chain.so/api#networks-supported

        :param network: SoChain network id e.g. BTCTEST
        """

        # SoChain supported networks
        assert network in ("btc", "btctest", "doge", "dogetest")

        # Monitored wallets list
        # wallet wallet_id -> {lastid, addresses}
        self.wallets = {}

        self.network = network
        self.connected = False
        self.init_pusher(self.pusher_app_key)
        self.transaction_thread = SochainTransctionThread(self)

    def init_wallets(self):
        """After we have a connection to the pusher server, include existing receiving addresses of wallets we have."""

        Wallet = self.transaction_updater.coin.wallet_model

        with self.transaction_updater.conflict_resolver.transaction() as session:
            for wallet in session.query(Wallet).all():
                self.include_wallet(wallet)

    def init_pusher(self, pusher_app_key):
        """Create a Pusher client listening to transaction notifications.
        """

        # Inherit logging level from this module
        self.pusher = SochainPusher(pusher_app_key, log_level=logger.level)

        def connected(data):
            self.connected = True
            self.transaction_thread.start()
            self.init_wallets()

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
        self.wallets[wallet.id] = dict(last_id=-1, addresses=set(), klass=wallet.__class__)

        #: Open transaction -> address mappings where we have not yet reached confirmation threshold
        self.transactions = {}
        self.include_addresses(wallet.id)

    def include_addresses(self, wallet_id):
        """Make addresses in a specific wallet to the monitoring list.

        """

        #: XXX: Optimize this to use batched transactions
        with self.transaction_updater.conflict_resolver.transaction() as session:

            assert wallet_id
            assert type(wallet_id) == int
            last_id = self.wallets[wallet_id]["last_id"]
            Wallet = self.wallets[wallet_id]["klass"]

            assert session.query(Wallet).count() > 0, "No wallets visible in Sochain monitor. Multithreading issue?".format(wallet_id)

            wallet = session.query(Wallet).filter_by(id=wallet_id).first()
            assert wallet is not None, "Could not load a specific wallet {}".format(wallet_id)

            addresses = wallet.get_receiving_addresses()

            # logger.debug("Checking wallet %d for %d addresses", wallet_id, addresses.count())

            for address in addresses.filter(wallet.Address.id > last_id, wallet.Address.archived_at is not None):  # noqa

                assert address.address not in self.wallets[wallet.id]["addresses"], "Tried to double monitor address {}".format(address.address)

                logger.info("Found address %d:%s to be monitored", address.id, address.address)

                self.wallets[wallet.id]["addresses"].add(address.address)
                self.wallets[wallet.id]["last_id"] = address.id
                self.subscribe_to_address(address.address)

    def include_transactions(self, wallet_id):
        """ Include all the wallet unconfirmed transactions on the monitored list. """

        # XXX: Better session and tx batching here
        with self.transaction_updater.conflict_resolver.transaction() as session:

            assert wallet_id
            assert type(wallet_id) == int
            Wallet = self.wallets[wallet_id]["klass"]

            wallet = session.query(Wallet).filter_by(id=wallet_id).first()
            assert wallet is not None, "Could not load a specific wallet {}".format(wallet_id)

            # Start subscribing to transactions still unfinished
            unconfirmed_txs = wallet.get_active_external_received_transcations()
            for tx in unconfirmed_txs:
                self.subscribe_to_transaction(tx.address, tx.txid)

    def finish_transaction(self, txid):
        """Stop watching the transaction.

        The transaction is so mature that we are no longer interested about it.
        """
        if txid in self.transactions:
            del self.transactions[txid]

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

    def subscribe_to_transaction(self, address, txid):
        """ Subscribe to get updates of a transaction.
        """
        # logger.info("Subscribed to new transaction {}".format(txid))
        # pusher_channel = "confirm_tx_{}_{}".format(self.network, txid)
        # channel = self.pusher.subscribe(pusher_channel)
        # channel.bind('balance_update', self.on_confirm_transaction)
        self.transactions[txid] = address

    def update_address_with_transaction(self, txid, address, amount, confirmations):
        """SoChain notified that there is new balance on an address."""

        # TODO: Get rid of global sessions, transaction manager
        tx_id, credited = self.transaction_updater.handle_address_receive(txid, address, amount, confirmations)

        # The transaction has become confirmed, no need to receive updates on it anymore
        if credited:
            self.finish_transaction(txid)

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

        balance_changed = Decimal(data["value"]["balance_change"])

        if balance_changed <= 0:
            # This was either send transactions (obviously initiated by us as we should control the private keys) or some other special transaction with no value. We are only interested in receiving transactions.
            return

        txid = data["value"]["tx"]["txid"]

        # We want notifications when the confirmation state changes
        self.subscribe_to_transaction(address, txid)

        amount = Decimal(data["value"]["value_received"])
        confirmations = 0  # SoChain fires on_balance_update on every noticed transaction broadcast. For actual incoming confirmations we need to listen to the transaction itself

        assert amount > 0

        self.update_address_with_transaction(txid, address, amount, confirmations)

    def refresh_addresses(self):
        """See if any new addresses have appeared in the database and put them on the monitoring list.
        """
        for wallet_id in self.wallets.keys():
            self.include_addresses(wallet_id)

    def run(self):
        """The main loop."""

        self.init_monitoring(self.pusher_app_key, self.network)
        self.running = True

        while self.running:
            # TODO: Have an interprocess notifications here so we don't need to poll for new addresses
            self.refresh_addresses()
            time.sleep(self.poll_period)

        self.close()

    def stop(self):
        self.running = False

        if self.transaction_thread:
            self.transaction_thread.stop()
