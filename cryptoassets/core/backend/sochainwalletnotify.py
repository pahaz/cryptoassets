"""Handle incoming transaction notifications using chain.so service."""

import json
import logging
import threading
import time
import requests
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


class SochainWalletNotifyHandler(threading.Thread, IncomingTransactionRunnable):
    """Detect and monitor incoming transactions using chain.so service.

    Open a websocket connection to read updates for transactions.
    """

    def __init__(self, pusher_app_key, transaction_updater, poll_period=0.2):
        """Configure a HTTP wallet notify handler server.

        :param transaction_updater: Instance of :py:class:`cryptoassets.core.backend.bitcoind.TransactionUpdater` or None

        :param network: Sochain Network id as a string "btctest"
        """
        threading.Thread.__init__(self)
        self.transaction_updater = transaction_updater
        self.pusher_app_key = pusher_app_key
        self.running = False
        self.network = transaction_updater.backend.network
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
            self.init_wallets()

        self.pusher.connection.bind('pusher:connection_established', connected)
        self.pusher.connect()

    def close(self):
        """
        """
        if self.connected:
            self.pusher.disconnect()
            self.connected = False

    def include_wallet(self, wallet):
        """ Add a wallet on the monitoring list.
        """
        assert wallet.id

        logger.debug("Initial inclusing of wallet %d receiving addresses in the monitoring", wallet.id)
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

            Address = wallet.coin_description.Address
            for address in addresses.filter(Address.id > last_id, Address.archived_at is not None):  # noqa

                if address.address in self.wallets[wallet.id]["addresses"]:
                    logger.warn("Tried to double monitor address %s, wallet id: %s, monitoring addresses since %s", address.address, wallet.id, last_id)
                    continue

                assert address.is_deposit(), "Tried to monitor non-deposit address"

                logger.info("Found address %d:%s to be monitored", address.id, address.address)

                self.wallets[wallet.id]["addresses"].add(address.address)
                self.wallets[wallet.id]["last_id"] = address.id
                self.subscribe_to_address(address.address)

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

    def on_balance_updated(self, data):
        """ chain.so tells us there should be a new transaction.

        Query block.io for authotarive transcation information.
        """

        data = json.loads(data)

        balance_changed = Decimal(data["value"]["balance_change"])

        if balance_changed <= 0:
            # This was either send transactions (obviously initiated by us as we should control the private keys) or some other special transaction with no value. We are only interested in receiving transactions.
            return

        txid = data["value"]["tx"]["txid"]

        self.transaction_updater.handle_wallet_notify(txid)

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
