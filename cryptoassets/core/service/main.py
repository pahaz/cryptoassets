"""Cryptoassets helper service is a standalone process managing cryptoasset backend connections and transaction updates.

Manages asynchronous tasks for sending and receiving cryptocurrency over various APIs. This includes

* Broadcasting transactions to the cryptocurrency network asynchronously

* Handle incoming transactions and write them to the database, calls your application via event handlers

* Updates confirmation counts of open transactions

"""

import sys
import datetime
import logging
import time
import signal

import pkg_resources
from apscheduler.schedulers.background import BackgroundScheduler

from ..app import CryptoAssetsApp
from ..app import Subsystem
from ..app import ALL_SUBSYSTEMS
from ..configure import Configurator
from ..backend.base import IncomingTransactionRunnable
from ..coin.registry import Coin

from ..tools import confirmationupdate
from ..tools import receivescan
from ..tools import broadcast

from ..utils import danglingthreads

from . import status
from . import defaultlogging


#: Must be instiated after the logging configure is passed in
logger = None


def splash_version():
    """Log out cryptoassets.core package version."""
    version = pkg_resources.require("cryptoassets.core")[0].version
    logger.info("cryptoassets.core version %s", version)


class Service:
    """Main cryptoassets helper service.

    This class runs *cryptoassets helper service* process itself and various command line utilities (*initialize-database*, etc.)

    We uses `Advanced Python Scheduler <http://apscheduler.readthedocs.org/>`_ to run timed jobs (broadcasts, confirmatino updates).

    Status server (:py:mod:`cryptoassets.core.service.status`) can be started for inspecting our backend connections are running well.

    """
    def __init__(self, config, subsystems=[Subsystem.database, Subsystem.backend], daemon=False, logging=True):
        """
        :param config: cryptoassets configuration dictionary

        :param subsystems: List of subsystems needed to initialize for this process

        :param daemon: Run as a service
        """
        self.app = CryptoAssetsApp(subsystems)

        #: Status server instance
        self.status_server = None

        #: coin name -> IncomingTransactionRunnable
        self.incoming_transaction_runnables = {}
        self.running = False
        self.last_broadcast = None
        self.receive_scan_thread = None

        #: How often we check out for outgoing transactions
        self.broadcast_period = 30

        # List of active running threads
        self.threads = []

        self.daemon = daemon

        self.config(config, logging_=logging)
        self.setup()

    def config(self, config, logging_):
        """Load configuration from Python dict.

        Initialize logging system if necessary.
        """
        self.configurator = Configurator(self.app, self)
        self.configurator.load_from_dict(config)
        if logging_:
            self.setup_logging(config)

        # Now logging is up'n'running and we can finally create logger for this Python module
        global logger
        logger = logging.getLogger(__name__)

        splash_version()

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

    def setup_logging(self, config):

        if not self.daemon or not config.get("service", {}).get("logging"):
            # Setup console logging if we run as a batch command or service config lacks logging
            defaultlogging.setup_stdout_logging()

    def setup_session(self):
        """Setup database sessions and conflict resolution."""
        self.app.setup_session()

    def initialize_db(self):
        """ """
        logger.info("Creating database tables for %s", self.app.engine.url)
        self.app.setup_session()
        self.app.create_tables()

    def setup_jobs(self):
        logger.debug("Setting up broadcast scheduled job")
        self.scheduler = BackgroundScheduler()
        self.broadcast_job = self.scheduler.add_job(self.poll_broadcast, 'interval', seconds=self.broadcast_period)
        self.open_transaction_job = self.scheduler.add_job(self.poll_network_transaction_confirmations, 'interval', minutes=1)

    def start_status_server(self):
        """Start the status server on HTTP.

        The server is previously set up by ``configure`` module.We need just to pass the status report generator of this service to it before starting it up.
        """
        if self.status_server:
            report_generator = status.StatusReportGenerator(self, self.app.conflict_resolver)
            logger.info("Starting status server %s with report generators %s", self.status_server, report_generator)
            self.status_server.start(report_generator)

            self.threads.append(self.status_server)

    def setup_incoming_notifications(self):
        """Start incoming transaction handlers.
        """

        assert self.app.conflict_resolver

        for name, coin, in self.app.coins.all():
            assert type(name) == str
            assert isinstance(coin, Coin)
            backend = coin.backend
            runnable = backend.setup_incoming_transactions(self.app.conflict_resolver, self.app.event_handler_registry)
            if runnable:
                logger.info("Setting up incoming transaction notifications for %s using %s", coin, runnable.__class__)
                assert isinstance(runnable, IncomingTransactionRunnable)
                if runnable:
                    self.incoming_transaction_runnables[name] = runnable
                    self.threads.append(runnable)

    def setup_sigterm(self):
        """Capture SIGTERM and shutdown on it."""

        old_sigint = None

        def term_handler(signum, frame):
            logger.info("Received SIGTERM")
            self.running = False

        def keyboard_handler(signum, frame):
            logger.info("Received SIGINT")
            self.running = False

            # Reove keyboard handler, so that CTRL+C twice does hard kill
            signal.signal(signal.SIGINT, old_sigint)

        # Set the signal handler and a 5-second alarm
        signal.signal(signal.SIGTERM, term_handler)
        old_sigint = signal.signal(signal.SIGINT, keyboard_handler)

    def poll_broadcast(self):
        """"A scheduled task to broadcast any new transactions to the bitcoin network.

        Each wallet is broadcasted in its own transaction.
        """
        self.last_broadcast = datetime.datetime.utcnow()

        for name, coin in self.app.coins.all():
            wallet_class = coin.wallet_model

            @self.app.conflict_resolver.managed_transaction
            def create_broadcasters(session):
                return [broadcast.Broadcaster(wallet, self.app.conflict_resolver, coin.backend) for wallet in session.query(wallet_class).all()]

            broadcasters = create_broadcasters()

            for broadcaster in broadcasters:
                broadcaster.do_broadcasts()

    def poll_network_transaction_confirmations(self):
        """Scan incoming open transactions.

        :return: Number of rescans attempted
        """

        rescans = 0
        for name, coin in self.app.coins.all():
            if coin.backend.require_tracking_incoming_confirmations():

                max_confirmation_count = coin.max_confirmation_count

                tx_updater = coin.backend.create_transaction_updater(self.app.conflict_resolver, self.app.event_handler_registry)
                confirmationupdate.update_confirmations(tx_updater, max_confirmation_count)
                rescans += 1

        return rescans

    def scan_received(self):
        """Scan through all received transactions, see if we missed some through walletnotify."""
        receivescan.scan(self.app.coins, self.app.conflict_resolver, self.app.event_handler_registry)

    def start_startup_receive_scan(self):
        self.receive_scan_thread = receivescan.BackgroundScanThread(self.app.coins, self.app.conflict_resolver, self.app.event_handler_registry)
        self.receive_scan_thread.start()

        self.threads.append(self.receive_scan_thread)

    def start(self):
        """Start cryptoassets helper service.

        Keep running until we get SIGTERM or CTRL+C.

        :return: Process exit code
        """
        logger.info("Starting cryptoassets helper service")
        self.running = True
        self.scheduler.start()
        for coin, runnable in self.incoming_transaction_runnables.items():
            logger.info("Starting incoming transaction notifications for %s", coin)
            runnable.start()

        self.start_status_server()
        self.start_startup_receive_scan()

        self.setup_sigterm()

        if self.daemon:
            # Leave cryptoassets helper service running
            return self.run_thread_monitor()
        else:
            # Testing from unit tests
            return

    def run_thread_monitor(self):
        """Run thread monitor until terminated by SIGTERM."""
        self.running = True

        while self.running:
            if not self.check_threads():
                logger.fatal("Shutting down due to failed thread")
                self.shutdown(unclean=True)
                return 2
            time.sleep(3.0)

        self.shutdown()

        return 0

    def check_threads(self):
        """Check all the critical threads are running and do shutdown if any of the threads has died unexpectly.

        :return: True if all threads stil alive
        """

        for thread in self.threads:
            if not thread.is_alive():

                # Assume all of our threads have thead.running attribute set False when they terminate their main loop normally
                if getattr(thread, "running", False) is True:
                    logger.error("Thread abnormally terminated %s", thread)
                    return False

        return True

    def shutdown(self, unclean=False):
        """Shutdown the service process.

        :param unclean: True if we terminate due to exception
        """

        logger.info("Attempting shutdown of cryptoassets helper service, unclean %s", unclean)
        self.running = False

        for runnable in self.incoming_transaction_runnables.values():
            runnable.stop()

        if self.scheduler.running:
            self.scheduler.shutdown()

        logger.info("Attempting of shutdown status server")
        if self.app.status_server:
            self.app.status_server.stop()
            self.app.status_server = None

        logger.debug("Checking for dangling threads")
        danglingthreads.check_dangling_threads()
        logger.debug("Quit")

# setuptools entry points


def parse_config_argv():
    if len(sys.argv) < 2:
        sys.exit("Usage: {} <configfile.config.yaml>".format(sys.argv[0]))

    config = Configurator.prepare_yaml_file(sys.argv[1])

    return config


def initializedb():

    config = parse_config_argv()
    service = Service(config, (Subsystem.database,))
    service.initialize_db()


def scan_received():

    config = parse_config_argv()
    service = Service(config, (Subsystem.database, Subsystem.backend, Subsystem.event_handler_registry))
    service.scan_received()


def helper():
    config = parse_config_argv()

    Configurator.setup_startup(config)

    service = Service(config, ALL_SUBSYSTEMS, daemon=True)
    exit_code = service.start()
    sys.exit(exit_code)
