# -*- coding: utf-8 -*-
"""Status displayer for cryptoassets service.
"""

import os
import threading
import codecs
from io import StringIO
import logging

from http.server import HTTPServer
from http.server import BaseHTTPRequestHandler

logger = logging.getLogger(__name__)


class TableCreator:
    """Simple HTML tabular info renderer.

    Totally unsafe, unprofessinal, use only for debug purposes.
    """

    def __init__(self, buffer):
        self.buffer = buffer

    def open(self, *columns):
        print("<style>th, td {text-align: left; vertical-align: top; padding-bottom: 0.5em; padding-right: 0.5em;}</style>", file=self.buffer)
        print("<table>", file=self.buffer)
        print("<tr>", file=self.buffer)
        for col in columns:
            print("<th>{}</th>".format(col), file=self.buffer)
        print("</tr>", file=self.buffer)

    def row(self, *data):
        print("<tr>", file=self.buffer)
        for d in data:
            print("<td>{}</td>".format(d), file=self.buffer)
        print("</tr>", file=self.buffer)

    def close(self):
        print("</table>", file=self.buffer)


class StatusReportGenerator:
    """Generate status report of running cryptoassets service.

    Output some useful status information when called from command line with ``curl``.
    """

    def __init__(self, service):
        self.service = service

    def accounts(self, output):
        """Dump all account data. """
        t = TableCreator(output)

        session = self.service.app.open_readonly_session()

        try:
            t.open("Currency", "id", "name", "balance", "address count", "received tx count", "sent tx count")
            for coin_name, coin in self.service.app.coins.all():
                Account = coin.account_model
                # TODO: optimize counting
                # http://stackoverflow.com/questions/19484059/sqlalchemy-query-for-object-with-count-of-relationship
                for acc in session.query(Account).all():
                    t.row(coin_name, acc.id, acc.name, acc.balance, len(acc.addresses), len(acc.received_transactions), len(acc.sent_transactions))
                    output.flush()
            t.close()

        finally:
            session.close()

    def transactions(self, output):
        c = TableCreator(output)

        session = self.service.app.open_readonly_session()

        try:
            c.open("Currency", "id", "txid", "state", "amount", "label", "confirmations", "created_at", "credited_at", "processed_at", "wallet", "sending account", "receiving account")
            for coin_name, coin in self.service.app.coins.all():
                Transaction = coin.transaction_model
                # TODO: optimize counting
                # http://stackoverflow.com/questions/19484059/sqlalchemy-query-for-object-with-count-of-relationship
                for t in session.query(Transaction).all():
                    # TODO: remove confirmations when cryptocurrency does not support it
                    c.row(coin_name, t.id, t.txid, t.state, t.amount, t.label, t.confirmations, t.created_at, t.credited_at, t.processed_at, t.wallet.id, t.sending_account and t.sending_account.id, t.receiving_account and t.receiving_account.id)
                    output.flush()
            c.close()

        finally:
            session.close()

    def addresses(self, output):
        t = TableCreator(output)

        session = self.service.app.open_readonly_session()

        try:
            t.open("Currency", "id", "address", "account_id", "name", "balance")
            for coin_name, coin in self.service.app.coins.all():
                Address = coin.address_model
                # TODO: optimize counting
                # http://stackoverflow.com/questions/19484059/sqlalchemy-query-for-object-with-count-of-relationship
                for addr in session.query(Address).all():
                    t.row(coin_name, addr.id, addr.address, addr.account.id, addr.label, addr.balance)
                    output.flush()
            t.close()

        finally:
            session.close()

    def wallets(self, output):
        t = TableCreator(output)

        session = self.service.app.open_readonly_session()

        try:
            t.open("Currency", "id", "accounts", "balance")
            for coin_name, coin in self.service.app.coins.all():
                Wallet = coin.wallet_model
                # TODO: optimize counting
                # http://stackoverflow.com/questions/19484059/sqlalchemy-query-for-object-with-count-of-relationship
                for w in session.query(Wallet).all():
                    t.row(coin_name, w.id, len(w.accounts), w.balance)
                    output.flush()
            t.close()

        finally:
            session.close()

    def index(self, output):
        """Return plaintext status output."""
        service = self.service

        t = TableCreator(output)

        t.open("coin", "alive", "hot wallet", "last incoming tx notification", "last broadcast", "backend last success", "backend error count")
        for coin, runnable in service.incoming_transaction_runnables.items():
            backend = self.service.app.coins.get(coin).backend
            hot_wallet_balance = backend.get_backend_balance()
            alive = runnable.is_alive()
            last_notification = runnable.transaction_updater.last_wallet_notify
            t.row(coin, alive, hot_wallet_balance, last_notification, "TODO", "TODO", "TODO")

        t.close()

        print("<p>Last transaction broadcast (UTC): {}</p>".format(service.last_broadcast), file=output)


class StatusHTTPServer(threading.Thread):
    """

    http://pymotw.com/2/BaseHTTPServer/
    """

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

            def nav(self, writer):
                """
                """

                # Allow upstream web server to tell in which location our pages are
                prefix = self.headers.get('X-Status-Server-Location', "")

                def link(href, name):
                    print("<a href='{}{}'>[ {} ]</a> ".format(prefix, href, name), file=writer)

                print("<p>", file=writer)
                link("/", "Main")
                link("/accounts", "Accounts")
                link("/addresses", "Addresses")
                link("/transactions", "Transactions")
                link("/wallets", "Wallets")
                print("</p>", file=writer)

            def do_GET(self):
                """Handle responses to status pages."""

                # Allow upstream web server to tell in which location our pages are
                prefix = self.headers.get('X-Status-Server-Location', "")

                # What pages we serve
                paths = {
                    "{}/".format(prefix): report_generator.index,
                    "{}/accounts".format(prefix): report_generator.accounts,
                    "{}/addresses".format(prefix): report_generator.addresses,
                    "{}/transactions".format(prefix): report_generator.transactions,
                    "{}/wallets".format(prefix): report_generator.wallets
                }

                func = paths.get(self.path)
                if not func:
                    self.send_error(404)
                    return

                self.send_response(200, "OK")
                self.send_header("Content-type", "text/html; charset=utf-8")
                self.end_headers()

                # http://www.macfreek.nl/memory/Encoding_of_Python_stdout
                writer = codecs.getwriter('utf-8')(self.wfile, 'strict')
                self.nav(writer)
                func(writer)

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

