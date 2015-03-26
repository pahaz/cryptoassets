"""Handle notifications for incoming transactions using block.io websockets API.

https://block.io/docs/notifications

This will spin off a thread opening a websocket connection to block.io and listening for incoming events.

This is done using `websocket-client library <https://pypi.python.org/pypi/websocket-client>`_.

Options
---------

:param class: Always ``cryptoassets.core.backend.blockiowebhook.BlockIoWebhookNotifyHandler``

:param url: To which public URL your webhook handler is mapped. The URL must not be guessable and must cointain random string, so that malicious actors cannot spoof incoming transaction requests.

:param ip: Bound IP address. Default 127.0.0.1 (localhost).

:parma port: Bound port. Default 11211.

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

        # Fix logging level for websockets
        from websocket._core import enableTrace

        if logger.level < logging.WARN:
            enableTrace(True)

        self.ws = websocket.WebSocketApp("wss://n.block.io/", on_open=self.on_open, on_message=self.on_message)

        threading.Thread.__init__(self)

    def on_open(self, ws):
        """ """
        logger.debug("websocket connection to block.io open")
        self.listening = True
        ws.send(json.dumps({
            "network": self.transaction_updater.backend.network,
            "type": "new-transactions"
        }))

    def on_message(self, ws, message):
        """ """
        message = json.loads(message)
        logger.debug("Got msg %s, ready %s, listening %s", message, self.ready, self.listening)
        if message.get("status") == "success" and self.listening:
            self.ready = True

    def run(self):
        self.running = True
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
        if self.ws:
            self.ws.close()