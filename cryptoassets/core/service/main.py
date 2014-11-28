"""A cryptoassets helper service.

Manages asynchronous tasks for sending and receiving cryptocurrency
over various APIs. This includes

* Broadcasting transactions to the cryptocurrency network asynchronously

* Handle incoming transactions and write them to the database
"""

import datetime
import logging
import transaction

from apscheduler.schedulers.background import BackgroundScheduler

from .. import configure
from ..backend import registry
from ..backend.base import IncomingTransactionRunnable

from ..coin import registry as coin_registry

from ..models import DBSession
from . import status


logger = logging.getLogger(__name__)


class Service:
    """Main cryptoassets helper service.

    You can launch this as a command line job, or wrap this to be started through your Python framework (e.g. Django)
    """
    def __init__(self, config):
        """
        :param config: cryptoassets configuration dictionary
        """
        logger.info("Setting up cryptoassets service")

        self.incoming_transaction_runnables = {}
        self.running = False
        self.last_broadcast = None
        self.status_http_server = None

        configure.load_from_dict(config)
        self.setup_jobs()
        self.setup_incoming_notifications()

    def setup_jobs(self):
        logger.info("Setting up broadcast scheduled job")
        self.scheduler = BackgroundScheduler()
        self.broadcast_job = self.scheduler.add_job(self.broadcast, 'interval', minutes=2)

    def start_status_server(self):
        """Start the status server on HTTP.

        The server is previously set up by ``configure`` module.We need just to pass the status report generator of this service to it before starting it up.
        """
        if status.status_http_server:
            report_generator = status.StatusReportGenerator(self)
            status.status_report_generator = report_generator
            logger.info("Starting status server %s with report generators %s", status.status_http_server, status.status_report_generator)
            status.status_http_server.start()

    def setup_incoming_notifications(self):
        """Start incoming transaction handlers.
        """
        for coin, backend in registry.all():
            runnable = backend.setup_incoming_transactions(DBSession)
            logger.info("Setting up incoming transaction notifications for %s using %s", coin, runnable.__class__)
            assert isinstance(runnable, IncomingTransactionRunnable)
            if runnable:
                self.incoming_transaction_runnables[coin] = runnable

    def broadcast(self):
        """"A scheduled task to broadcast any new transactions to the bitcoin network.

        Each wallet is broadcasted in its own transaction.
        """
        self.last_broadcast = datetime.datetime.utcnow()

        for coin in coin_registry.all():
            wallet_class = coin_registry.get_wallet_model(coin)
            with transaction.manager:
                wallet_ids = [wallet.id for wallet in DBSession.query(wallet_class).all()]

            for wallet_id in wallet_ids:
                with transaction.manager:
                    wallet = DBSession.query(wallet_class).get(wallet_id)
                    logger.info("Broadcasting transactions for wallet class %s wallet %d:%s", wallet_class, wallet.id, wallet.name)
                    outgoing = wallet.broadcast()
                    logger.info("%d transactionsn send", outgoing)

    def start(self):
        """
        """
        logger.info("Starting cryptoassets helper service")
        self.running = True
        self.scheduler.start()
        for coin, runnable in self.incoming_transaction_runnables.items():
            logger.info("Starting incoming transaction notifications for %s", coin)
            runnable.start()
        self.start_status_server()

    def shutdown(self):

        logger.info("Attempting shutdown of cryptoassets helper service")
        self.running = False

        for runnable in self.incoming_transaction_runnables.values():
            runnable.stop()

        if self.scheduler.running:
            self.scheduler.shutdown()

        logger.info("Attempting of shutdown status server")
        if status.status_http_server:
            status.status_http_server.stop()
            status.status_http_server = None

