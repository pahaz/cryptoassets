"""Handle notifications for incoming transactions using block.io HTTPO POST webhook API.

https://block.io/docs/notifications

This will spin off a HTTP server in a separate IP and port to listen to HTTP requests made by the block.io.
You need to specify an external URL how block.io can reach the public IP address of your server.

Options
---------

:param class: Always ``cryptoassets.core.backend.blockiowebhook.BlockIoWebhookNotifyHandler``

:param url: To which public URL your webhook handler is mapped. The URL must not be guessable and must cointain random string, so that malicious actors cannot spoof incoming transaction requests.

:param ip: Bound IP address. Default 127.0.0.1 (localhost).

:parma port: Bound port. Default 33233.

Securing the webhooks
----------------------------

Do not expose webhook service port directly to the internet. Instead, use your web server to create a reverse proxy behind a hidden URL, so you can safely receive notifications from block.io.

**HTTPS support through Nginx**

Here is an example Nginx web server configuration how decode HTTPS and then forward block.io requets to the upstream server running in the cryptoassets helper service process::

    # Secret block.io webhook endpoint
    location /blockio-account-nofity/xyz {
        proxy_set_header   Host $host;
        proxy_set_header   X-Real-IP $remote_addr;
        proxy_set_header   X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Host $server_name;
        proxy_set_header   X-Forwarded-Proto $scheme;
        proxy_pass http://localhost:33233;
    }

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

import block_io


from .base import IncomingTransactionRunnable


logger = logging.getLogger(__name__)


class BlockIoWebhookRequestHandler(BaseHTTPRequestHandler):
    # Handle block.io webhook HTTP POST requests.

    def log_request(self, code=None, size=None):
        if code != 200:
            logger.error("BlockIoWebhookRequestHandler puked %d", code)

    def validate_url(self):
        """Make sure the user cannot post fake transaction update without knowing the secret shared URL."""
        valid_path = urlparse(self.server.endpoint_url).path

        # Normalize ending slash usage
        valid_path = valid_path.rstrip("/")
        path = self.path.rstrip("/")

        if path != valid_path:
            raise RuntimeError("Got block.io webhook POST to {}, expected URL {}", self.path, self.server.endpoint_url)

    def do_POST(self):

        # Make sure something nefarious is not going on
        self.validate_url()

        raw = None
        try:

            # http://stackoverflow.com/a/12731208/315168
            # Extract and print the contents of the POST
            length = int(self.headers['Content-Length'])

            assert length < 1024*1024, "Got webhook request larger than one megabyte"

            # Make sure we read most X bytes
            raw = self.rfile.read(length).decode('utf-8')
            data = json.loads(raw)

            if data["type"] == "ping":
                logger.debug("block.io webhook pinged us")
            else:
                logger.debug("block.io incoming transaction notification")
                # {'notification_id': '8a531bc3ecf111ac9c5496f5', 'data': {'outputs': [{'output_no': 0, 'address': '2MsFJrz688gkpQDZxureANRR2LVaz3iQdSu', 'script': 'OP_HASH160 000411991252e51ae1f71d0bff1d4787f8a574ab OP_EQUAL', 'type': 'scripthash', 'amount': '100000.00000000'}, {'output_no': 1, 'address': '2MsQug2PDbor2ndqYu9MxMij3MZFZ3EkGk9', 'script': 'OP_HASH160 01d4df05a673fc46698c4d2effdac931d7600252 OP_EQUAL', 'type': 'scripthash', 'amount': '14099941.00000000'}], 'block_no': None, 'inputs': [{'amount': '14199942.00000000', 'script': '0 3044022062f9a86b8e42fe6ea0aba3e3d9fa89f0e0e3d421a50d74398cd592be20ea38f902204a2443ecb38ce6293ead2a879ecd36dd2cc5e0bf4c190d1fc0b3608f7429702401 3045022100d627dd9ec231d73e189fe11007514755e1899fe291465f17c48c067909c62a3c02204fd83347905de9d8ccb4f6bde95687602bc697854ae04784fca3aed989e11db601 522103abf01d993487a683db0a788298e176624b8530c9481b8f3f17eaec015a6e8c882103ec7f0dd153f1fa7f2fd5d6b331796298ebd0a657950c70cbb58eac34c7b475f352ae', 'address': '2MsQug2PDbor2ndqYu9MxMij3MZFZ3EkGk9', 'previous_output_no': 1, 'previous_txid': '6a35025b267e7c110d3859b8b21c5cd8fb4181610df122b7dc413f4319d6cfb8', 'input_no': 0, 'type': 'scripthash'}], 'is_green': True, 'received_at': 1427313326, 'block_hash': None, 'block_time': None, 'confirmations': 0, 'network_fee': '1.00000000', 'amount_received': '14199941.00000000', 'txid': 'a53050c9534a24221a4c2b41babc06652e803919e21ed6c7e244a292244368fb', 'network': 'DOGETEST'}, 'delivery_attempt': 1, 'type': 'new-transactions', 'created_at': 1427313326}
                txid = data["data"]["txid"]
                if data["delivery_attempt"] > 1:
                    logger.warn("Did not get block.io webhook delivery on the first attempt, got attempt %d, txid %s", data["delivery_attempt"], txid)
                self.handle_tx_update(txid)

            self.send_response(200, "OK")
            self.end_headers()
            return ""
        except Exception as e:
            logger.error("Error handling incoming walletnotify %s", raw)
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
            raise RuntimeError("Got txupdate, but no transaction_updater instance available, %s", txid)


class BlockIoWebhookNotifyHandler(threading.Thread, IncomingTransactionRunnable):
    # Run a webhook endpoint web server in a background thread

    def __init__(self, transaction_updater, url, ip="127.0.0.1", port=33233):

        assert url, "You must give a URL for block.io webhooks"

        self.transaction_updater = transaction_updater
        self.running = True
        self.ip = ip
        self.port = int(port)
        self.ready = False
        self.url = url
        self.block_io_notification_id = None

        # The backend must be block.io kind
        self.block_io = transaction_updater.backend.block_io

        server_address = (self.ip, self.port)

        logger.debug("Starting HTTP server listening to block.io webhook notifications at {}:{} for URL {}".format(self.ip, self.port, self.url))

        try:
            self.httpd = HTTPServer(server_address, BlockIoWebhookRequestHandler)
            self.httpd.transaction_updater = transaction_updater
            self.httpd.endpoint_url = url
        except OSError as e:
            raise RuntimeError("Could not start block.io notification webhook server at {}:{}".format(self.ip, self.port)) from e

        threading.Thread.__init__(self)

    def run(self):
        self.running = True
        self.ready = True

        def blockio_webhook_init(self):
            # Tell block.io to start bombing us. This must happen after the HTTP server is started, so we do it asyncronously
            deadline = time.time() + 2.0

            assert self.httpd, "Tried to initialize block.io webhooks without having valid HTTP server"

            # Delete existing notification, as the block.io backend can only support one URL per notification type at time and we may have left one around from unclean shutdown / sharing the same wallet
            try:
                notification_data = self.block_io.get_notifications()
            except block_io.BlockIoAPIError:
                # Failed: No valid notifications found for Network=DOGETEST
                notification_data = None

            if notification_data:
                # Get rid of the existing webhook
                for notification in notification_data["data"]:
                    if notification["type"] == "account":
                        self.block_io.delete_notification(notification_id=notification["notification_id"])

            # re(set) the notification handler to point to our webhook
            notification_data = self.block_io.create_notification(type="account", url=self.url)
            self.block_io_notification_id = notification_data["data"]["notification_id"]
            logger.info("block.io webhook notification id is %s", self.block_io_notification_id)
            logger.info("Notifications are %s", self.block_io.get_notifications())

        blockio_async_init = threading.Thread(target=blockio_webhook_init, args=(self,))
        blockio_async_init.start()
        self.httpd.serve_forever()
        self.running = False

    def stop(self):
        if self.httpd:
            logger.info("Shutting down block.io HTTP webhook server %s", self)
            self.httpd.shutdown()
            self.httpd = None

        # Stop block.io bugging us
        if self.block_io_notification_id:
            logger.info("Deleting block.io HTTP webhook %s", self.block_io_notification_id)
            self.block_io.delete_notification(notification_id=self.block_io_notification_id)
            self.block_io_notification_id = None
