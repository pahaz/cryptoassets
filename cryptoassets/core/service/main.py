"""A cryptoassets helper service.

Manages asynchronous tasks for sending and receiving cryptocurrency
over various APIs. This includes

* Broadcasting transactions to the cryptocurrency network asynchronously

* Handle incoming transactions and write them to the database
"""

import logging

from apscheduler.schedulers.background import BackgroundScheduler

from .. import configure
from ..backend import registry

from ..models import DBSession


logger = logging.getLogger(__name__)


class Service:
    """Main cryptoassets helper service.

    You can launch this as a command line job, or wrap this to be started through your Python framework (e.g. Django)
    """
    def __init__(self, config):
        """
        :param config: cryptoassets configuration dictionary
        """
        configure.load_from_dict(config)
        self.setup_jobs()
        self.setup_incoming_notifications()

        self.incoming_transaction_runnables = []

    def setup_jobs(self):
        self.scheduler = BackgroundScheduler()
        self.broadcast_job = self.scheduler.add_job(self.broadcast, 'interval', minutes=2)

    def setup_incoming_notifications(self):
        """
        """

        for coin, backend in registry.all():
            runnable = backend.setup_incoming_transactions(DBSession)
            if runnable:
                self.incoming_transaction_runnables.append(runnable)

    def broadcast():
        for wallet in DBSession.query():
            pass

    def run():
        pass

    def shutdown(self):
        for runnable in self.incoming_transaction_runnables:
            runnable.stop()

        self.scheduler.shutdown()




