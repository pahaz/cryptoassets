"""Handle walletnofify notificatians from bitcoind through curl / wget HTTP request.

This is useful in cases where *bitcoind* or alike is running on a remote server and you wish to receive walletnotifications from there. In this case, you can set up SSH tunnel and forward the locally started HTTP wallet notify listener to the bitcoind server.

Creates a HTTP server running in port 28882 (default). To receive a new transaction notification do a HTTP POST to this server::

    curl --data "txid=%s" http://localhost:28882

E.g. in ``bitcoind.conf``::

    walletnotify=curl --data "txid=%s" http://localhost:28882

Options
---------

:param class: Always ``cryptoassets.core.backend.httpwalletnotify.HTTPWalletNotifyHandler``

:param ip: Bound IP address. Default 127.0.0.1 (localhost).

:parma port: Bound port. Default 28882.

Testing
--------

To test that the wallet notifications are coming through

1. Make sure ``cryptoassetshelper`` service is running

2. Do ``curl --data "txid=foobar" http://localhost:28882`` on the server where *bitcoind* is running

3. You should see in the logs of ``cryptoassetshelper``: *Error communicating with bitcoind API call gettransaction: Invalid or non-wallet transaction id*

"""

import os
import logging
import fcntl
import time
import threading
import datetime
import cgi
from http.server import HTTPServer
from http.server import BaseHTTPRequestHandler
from cgi import parse_header
from cgi import parse_multipart
from urllib.parse import parse_qs

from .base import IncomingTransactionRunnable


logger = logging.getLogger(__name__)


class WalletNotifyRequestHandler(BaseHTTPRequestHandler):
    """Very crude HTTP POST processor.

    Extra txid from the POST request.
    """
    def do_POST(self):

        try:
            ctype, pdict = parse_header(self.headers['content-type'])
            if ctype == 'multipart/form-data':
                postvars = parse_multipart(self.rfile, pdict)
            elif ctype == 'application/x-www-form-urlencoded':
                length = int(self.headers['content-length'])
                postvars = parse_qs(self.rfile.read(length), keep_blank_values=1)
            else:
                postvars = {}

            txid = postvars[b"txid"][0].decode("utf-8")

            self.handle_tx_update(txid)

            self.send_response(200, "OK")
            self.end_headers()
            return ""
        except Exception as e:
            logger.error("Error handling incoming walletnotify %s", postvars)
            logger.exception(e)
            self.send_response(500, "Internal server error")
            self.end_headers()
            raise e

    def handle_tx_update(self, txid):
        """Handle each transaction notify as its own db commit."""

        # Each address object is updated in an isolated transaction,
        # thus we need to pass the db transaction manager to the transaction updater
        transaction_updater = self.server.transaction_updater
        if transaction_updater is not None:
            transaction_updater.handle_wallet_notify(txid)
        else:
            logger.warn("Got txupdate, but no transaction_updater instance available, %s", txid)


class HTTPWalletNotifyHandlerBase:

    def __init__(self, transaction_updater, ip, port):
        self.transaction_updater = transaction_updater
        self.running = True
        self.ip = ip
        self.port = port
        self.ready = False

        server_address = (self.ip, self.port)
        try:
            self.httpd = HTTPServer(server_address, WalletNotifyRequestHandler)
            self.httpd.transaction_updater = transaction_updater
        except OSError as e:
            raise RuntimeError("Could not start cryptoassets HTTP walletnotify notifiaction server at {}:{}".format(self.ip, self.port)) from e

    def run(self):
        self.running = True
        self.ready = True
        self.httpd.serve_forever()
        self.running = False

    def stop(self):
        if self.httpd:
            logger.info("Shutting down HTTP walletnofify server %s", self)
            self.httpd.shutdown()
            self.httpd = None


class HTTPWalletNotifyHandler(HTTPWalletNotifyHandlerBase, threading.Thread, IncomingTransactionRunnable):
    """Handle walletnofify notificatians from bitcoind through curl / wget HTTP request."""

    def __init__(self, transaction_updater, ip, port):
        """Configure a HTTP wallet notify handler server.

        :param transaction_updater: Instance of :py:class:`cryptoassets.core.backend.bitcoind.TransactionUpdater` or None

        :param ip: Bound IP address

        :param port: TCP/IP port
        """
        HTTPWalletNotifyHandlerBase.__init__(self, transaction_updater, ip, port)
        threading.Thread.__init__(self)
