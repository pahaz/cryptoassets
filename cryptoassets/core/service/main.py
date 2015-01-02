"""A cryptoassets helper service.

Manages asynchronous tasks for sending and receiving cryptocurrency
over various APIs. This includes

* Broadcasting transactions to the cryptocurrency network asynchronously

* Handle incoming transactions and write them to the database
"""

import sys
import datetime
import logging
import transaction
import time

import pkg_resources
from apscheduler.schedulers.background import BackgroundScheduler

from ..app import CryptoAssetsApp
from ..app import Subsystem
from ..configure import Configurator
from ..backend.base import IncomingTransactionRunnable
from ..coin.registry import Coin
from . import status
from . import defaultlogging


logger = logging.getLogger(__name__)


def splash_version():
    version = pkg_resources.require("cryptoassets.core")[0].version
    logger.info("cryptoassets.core version %s", version)


class Service:
    """Main cryptoassets helper service.

    You can launch this as a command line job, or wrap this to be started through your Python framework (e.g. Django)
    """
    def __init__(self, config, subsystems=[Subsystem.database, Subsystem.backend]):
        """
        :param config: cryptoassets configuration dictionary

        :param subsystems: List of subsystems needed to initialize for this process
        """
        self.app = CryptoAssetsApp(subsystems)

        #: Status server instance
        self.status_server = None

        #: coin name -> IncomingTransactionRunnable
        self.incoming_transaction_runnables = {}
        self.running = False
        self.last_broadcast = None

        self.config(config)
        self.setup()

    def config(self, config):
        self.configurator = Configurator(self.app)
        self.configurator.load_from_dict(config)

    def setup(self):
        """Start background threads and such."""
        if Subsystem.broadcast in self.app.subsystems:
            self.setup_jobs()

        if Subsystem.database in self.app.subsystems:
            self.setup_session()

        if Subsystem.incoming_transactions in self.app.subsystems:
            self.setup_incoming_notifications()

        # XXX: We are aliasing here, because configurator can only touch app object. Need to figure out something cleaner.
        self.status_server = self.app.status_server

    def setup_session(self):
        """Setup database sessions and conflict resolution."""
        self.app.setup_session()

    def initialize_db(self):
        """ """
        logger.info("Creating database tables for %s", self.app.engine.url)
        self.app.setup_session()
        self.app.create_tables()

    def setup_jobs(self):
        logger.info("Setting up broadcast scheduled job")
        self.scheduler = BackgroundScheduler()
        self.broadcast_job = self.scheduler.add_job(self.broadcast, 'interval', minutes=2)

    def start_status_server(self):
        """Start the status server on HTTP.

        The server is previously set up by ``configure`` module.We need just to pass the status report generator of this service to it before starting it up.
        """
        if self.status_server:
            report_generator = status.StatusReportGenerator(self, self.app.conflict_resolver)
            logger.info("Starting status server %s with report generators %s", self.status_server, report_generator)
            self.status_server.start(report_generator)

    def setup_incoming_notifications(self):
        """Start incoming transaction handlers.
        """

        assert self.app.session
        assert self.app.conflict_resolver

        for name, coin, in self.app.coins.all():
            assert type(name) == str
            assert isinstance(coin, Coin)
            backend = coin.backend
            runnable = backend.setup_incoming_transactions(self.app.conflict_resolver, self.app.notifiers)
            if runnable:
                logger.info("Setting up incoming transaction notifications for %s using %s", coin, runnable.__class__)
                assert isinstance(runnable, IncomingTransactionRunnable)
                if runnable:
                    self.incoming_transaction_runnables[name] = runnable

    def broadcast(self):
        """"A scheduled task to broadcast any new transactions to the bitcoin network.

        Each wallet is broadcasted in its own transaction.
        """
        self.last_broadcast = datetime.datetime.utcnow()

        session = self.app.session

        for name, coin in self.app.coins.all():
            wallet_class = coin.wallet_model
            with transaction.manager:
                wallet_ids = [wallet.id for wallet in session.query(wallet_class).all()]

            for wallet_id in wallet_ids:
                with transaction.manager:
                    wallet = session.query(wallet_class).get(wallet_id)
                    logger.info("Broadcasting transactions for wallet class %s wallet %d:%s", wallet_class, wallet.id, wallet.name)
                    outgoing = wallet.broadcast()
                    logger.info("%d transactionsn send", outgoing)

    def rescan(self):
        """Scan through all bitcoind transactions, see if we missed some through walletnotify."""
        for name, coin in self.app.coins.all():
            logger.info("Scanning through all transactions for %s", name)
            tx_updater = coin.backend.create_transaction_updater(self.app.session, self.app.notifiers)
            transaction_manager = transaction.manager
            tx_updater.rescan_all(transaction_manager)

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
        if self.app.status_server:
            self.app.status_server.stop()
            self.app.status_server = None

# setuptools entry points


def parse_config_argv():
    if len(sys.argv) < 2:
        sys.exit("Usage: {} <configfile.config.yaml>".format(sys.argv[0]))

    config = Configurator.prepare_yaml_file(sys.argv[1])

    return config


def initializedb():
    defaultlogging.setup_stdout_logging()
    splash_version()
    config = parse_config_argv()
    service = Service(config, (Subsystem.database,))
    service.initialize_db()


def helper():
    config = parse_config_argv()
    Configurator.load_standalone_from_dict(config)
    service = Service(config, (Subsystem.database, Subsystem.status_server, Subsystem.backend, Subsystem.notifiers))
    service.start()
    while True:
        time.sleep(1)
