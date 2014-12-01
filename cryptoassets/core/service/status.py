"""Status displayer for cryptoassets service.
"""

import os
import threading
from io import StringIO
import logging

from http.server import HTTPServer
from http.server import BaseHTTPRequestHandler


logger = logging.getLogger(__name__)


class StatusReportGenerator:
    """Generate status report of running cryptoassets service.

    Output some useful status information when called from command line with ``curl``.
    """

    def __init__(self, service):
        self.service = service

    def get_plaintext(self):
        """Return plaintext status output."""
        output = StringIO()
        service = self.service
        print("Cryptoassets helper process id: {}".format(os.getpid()), file=output)
        print("".format(service.last_broadcast), file=output)
        print("Last transaction broadcast (UTC): {}".format(service.last_broadcast), file=output)
        print("", file=output)
        print("Incoming transaction monitors", file=output)
        for coin, runnable in service.incoming_transaction_runnables.items():
            if not runnable.is_alive():
                print("%s is dead".format(coin), file=output)
            else:
                last_notification = runnable.transaction_updater.last_wallet_notify
                print("%s is alive, last notification %s".format(coin, last_notification), file=output)

        return output.getvalue()


class StatusHTTPServer(threading.Thread):

    def __init__(self, ip, port):
        threading.Thread.__init__(self)
        self.httpd = None
        self.status_report = None
        self.ip = ip
        self.port = port
        self.running = False
        self.ready = False

    def start(self, report_generator):

        class StatusGetHandler(BaseHTTPRequestHandler):

            counter = 0

            def do_GET(self):
                self.send_response(200, "OK")
                self.end_headers()
                report_generator.get_plaintext()

        server_address = (self.ip, self.port)
        try:
            self.httpd = HTTPServer(server_address, StatusGetHandler)
        except OSError as e:
            raise RuntimeError("Could not start cryptoassets helper service status server at {}:{}".format(self.ip, self.port)) from e

        threading.Thread.start(self)

    def run(self):
        self.running = True
        self.ready = True
        self.httpd.serve_forever()
        self.running = False

    def stop(self):
        if self.httpd and self.running:
            logger.info("Shutting down HTTP status server %s", self)
            self.httpd.shutdown()
            self.httpd = None

