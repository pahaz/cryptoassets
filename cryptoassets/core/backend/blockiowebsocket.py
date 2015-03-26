"""Handle notifications for incoming transactions using block.io websockets API.

https://block.io/docs/notifications

This will spin off a thread opening a websocket connection to block.io and listening for incoming events.

We use `websocket-client library <https://pypi.python.org/pypi/websocket-client>`_ for websockets communications from Python.

Options
---------

:param class: Always ``cryptoassets.core.backend.blockiowebsocket.BlockIoWebsocketNotifyHandler``
"""

import threading
import logging
import time
import json

from http.server import HTTPServer
from http.server import BaseHTTPRequestHandler
from cgi import parse_header
from cgi import parse_multipart
from urllib.parse import parse_qs
from urllib.parse import urlparse

import websocket
import block_io


from .base import IncomingTransactionRunnable


logger = logging.getLogger(__name__)


class BlockIoWebsocketNotifyHandler(threading.Thread, IncomingTransactionRunnable):
    # Run a webhook endpoint web server in a background thread

    def __init__(self, transaction_updater):

        self.transaction_updater = transaction_updater
        self.running = True

        # Have we received initial ping ok from block.io
        self.ready = False

        # Have we initiated network listening
        self.listening = False

        # The backend must be block.io kind
        self.block_io = transaction_updater.backend.block_io

        #: We need a helper thread to notify us when new address becomes available. This is due to an API issue, as block.io needs new websocket message every time you want to subscribe to new addresses
        self.address_monitor = None

        # websocket module does not define proper loggers so we just disable this for now
        #
        # from websocket._core import enableTrace
        #
        # if logger.level < logging.WARN:
        #   enableTrace(True)

        self.ws = websocket.WebSocketApp("wss://n.block.io/", on_message=self.on_message)

        threading.Thread.__init__(self)

    def subscribe(self):
        """Start receiving account notifications."""
        self.listening = True
        network = self.transaction_updater.backend.network.upper()
        logger.debug("Subscribing to notifications on {}".format(network))

        data = {
            "api_key": self.transaction_updater.backend.api_key,
            "type": "account"
        }

        self.ws.send(json.dumps(data))

    def on_message(self, ws, message):
        """ """
        message = json.loads(message)

        if not self.listening:
            logger.debug("websocket connection to block.io open")
            self.subscribe()

        logger.debug("Got msg %s, ready %s, listening %s", message, self.ready, self.listening)
        if message.get("status") == "success" and self.listening:
            self.ready = True

        msg_type = message.get("type")

        if msg_type is None:
            # Initial connection success message
            pass
        elif msg_type == "ping":
            pass
        elif msg_type == "address":
            txid = message["data"]["txid"]
            self.handle_tx_update(txid)

    def run(self):
        self.running = True

        self.address_monitor = AddressMonitor(self, self.transaction_updater)
        self.address_monitor.start()

        self.ws.run_forever()

    def wait_until_ready(self, timeout=10):
        """Block the current thread until we are sure we can receive notifications."""

        deadline = time.time() + timeout
        while time.time() < deadline:
            if self.ready:
                return
            time.sleep(0.1)

        raise AssertionError("Could not start listening transactions within given time.")

    def stop(self):

        if self.address_monitor:
            self.address_monitor.stop()

        if self.ws:
            self.ws.close()

    def handle_tx_update(self, txid):
        """Handle each transaction notify as its own db commit."""

        # Each address object is updated in an isolated transaction,
        # thus we need to pass the db transaction manager to the transaction updater
        transaction_updater = self.transaction_updater
        if transaction_updater is not None:
            transaction_updater.handle_wallet_notify(txid)
        else:
            raise RuntimeError("Got txupdate, but no transaction_updater instance available, %s", txid)


class AddressMonitor(threading.Thread):
    """Monitor creation of new addresses and subscribe to events in them.

    Some backends require subscription refresh after new addresses have been created.

    ATM we need to poll database every second. We could make optimizatin for PostgreSQL using subscriptions.
    """

    def __init__(self, incoming_transactions_runnable, transaction_updater):

        # key: (coin, wallet_id tuple), value: count of addresses subscribed in that wallet
        self.incoming_transactions_runnable = incoming_transactions_runnable
        self.transaction_updater = transaction_updater
        self.previous_refreshed_last_address_id = None
        self.poll_period = 1.0
        threading.Thread.__init__(self)

    def scan(self):
        """Scan all wallets to see if we need to resubscribe."""

        Address = self.transaction_updater.coin.address_model

        with self.transaction_updater.conflict_resolver.transaction() as session:
            last_address_entry = session.query(Address).order_by(Address.id.desc())
            if getattr(last_address_entry, "id", None) != self.previous_refreshed_last_address_id:
                self.refresh()
                self.previous_refreshed_last_address_id = last_address_entry.id

    def refresh(self):
        logger.debug("Refreshing address subscriptions")
        self.incoming_transactions_runnable.subscribe()

    def run(self):
        """The main loop."""

        self.running = True

        logger.info("Starting address monitoring loop for %s", self.incoming_transactions_runnable)

        while self.running:
            # TODO: Have an interprocess notifications here so we don't need to poll for new addresses
            self.scan()
            time.sleep(self.poll_period)

    def stop(self):
        # XXX: Race condition, the websocket might close before us
        logger.info("Shutting down address monitoring loop for %s", self.incoming_transactions_runnable)
        self.running = False


def test_out():
    """Self-contained wallet monitor printing out websocket traffic and transactions.

    Usage:

        echo "from cryptoassets.core.backend.blockiowebsocket import test_out ; test_out()" | python3.4
    """
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.orm import scoped_session
    from sqlalchemy import create_engine

    from . import blockio
    from ..coin.registry import Coin
    from ..coin.dogecoin.models import coin_description as doge_description
    from ..utils.conflictresolver import ConflictResolver
    from .transactionupdater import TransactionUpdater

    # Setup dummy database + dogecoin database model
    coin = Coin(doge_description, max_confirmation_count=15, testnet=True)
    engine = create_engine("sqlite:////tmp/cryptoassets-websocket-blockio.sqlite")
    Session = scoped_session(sessionmaker(autocommit=False, autoflush=False, bind=engine))
    conflict_resolver = ConflictResolver(Session, retries=3)

    logging.basicConfig()
    backend = blockio.BlockIo(coin, "0266-c2b6-c2c8-ee07", "foobar123", network="DOGETEST")
    transaction_updater = TransactionUpdater(conflict_resolver, backend, coin, None)

    incoming_transactions_runnable = BlockIoWebsocketNotifyHandler(transaction_updater)
    incoming_transactions_runnable.start()
    incoming_transactions_runnable.wait_until_ready()
    print("Rock'n'roll, try sending to address 2MwCpNCnDpzyaSkq1MfVaYZB5Kmt5yv4gC6")
