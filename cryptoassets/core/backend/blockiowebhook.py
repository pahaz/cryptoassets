"""Handle notifications for incoming transactions using block.io webhook API.

https://block.io/docs/notifications

This will spin off a HTTP server in a separate IP and port to listen to HTTP requests made by the block.io.
You need to specify an external URL how block.io can reach the public IP address of your server.

*HTTPS support*

Here is an example Nginx web server configuration how decode HTTPS and then forward block.io requets to the upstream server running in the cryptoassets helper service process.

"""

import threading
import logging

from http.server import HTTPServer
from http.server import BaseHTTPRequestHandler
from cgi import parse_header
from cgi import parse_multipart
from urllib.parse import parse_qs

from .base import IncomingTransactionRunnable


logger = logging.getLogger(__name__)


class BlockIoWebhookRequestHandler(BaseHTTPRequestHandler):
    """Very crude HTTP POST processor.

    Extra txid from the POST request.
    """
    def do_POST(self):

        try:

            # http://stackoverflow.com/a/12731208/315168
            # Extract and print the contents of the POST
            length = int(self.headers['Content-Length'])
            post_data = parse_qs(self.rfile.read(length).decode('utf-8'))

            if "data" not in post_data:
                raise RuntimeError("Incoming POST did not contain data field: {}".format(post_data))

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


class BlockIoWebhookNotifyHandler(threading.Thread, IncomingTransactionRunnable):

    def __init__(self, transaction_updater, ip, port, url):
        self.transaction_updater = transaction_updater
        self.running = True
        self.ip = ip
        self.port = port
        self.ready = False
        self.url = url

        # The backend must be block.io kind
        self.block_io = transaction_updater.backend.block_io

        server_address = (self.ip, self.port)
        try:
            self.httpd = HTTPServer(server_address, BlockIoWebhookRequestHandler)
            self.httpd.transaction_updater = transaction_updater
        except OSError as e:
            raise RuntimeError("Could not start block.io notification webhook server at {}:{}".format(self.ip, self.port)) from e

        # Tell block.io to start boming us
        notification_data = self.block_io.create_notification(type="new_transaction", url=self.url)
        self.notification_key = notification_data["data"]["notification"]

        threading.Thread.__init__(self)

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

        # Stop block.io bugging us
        self.block_io.disable_notification(notification_key=self.notification_key)
