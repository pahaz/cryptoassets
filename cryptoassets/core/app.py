"""Cryptoassets application manager."""
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm import scoped_session

from .models import DBSession
from .models import Base

from .utils.enum import AutoNumber
from .utils.conflictresolver import ConflictResolver


class Subsystem(AutoNumber):
    """Enumerator for available cryptoassets library subsystems.

    Depending on your application entry point and user case, you might not want to initialize all features of cryptoassets framework within your Python application. For example, multiple web server processes cannot initialize status server each, but this functinonality is purposed for the daemon applications.
    """

    #: Initialize database connections
    database = ()

    #: Open HTTP status server running
    status_server = ()

    #: Try to connect to backend APIs
    backend = ()

    #: Start processes and threads for broadcasting outgoing transactions
    broadcast = ()

    #: Start processes and threads for walletnotify hooks
    incoming_transactions = ()

    #: Post notifications
    notifiers = ()


ALL_SUBSYSTEMS = Subsystem.__members__.values()


class CryptoAssetsApp:
    """This class ties all strings together to make a runnable cryptoassets app."""

    def __init__(self, subsystems=[Subsystem.database, Subsystem.backend]):
        """Initialize a cryptoassets framework.

        :param subsystems: Give the list of subsystems you want to initialize. Because the same configuration file can be used by e.g. both web server and command line application, and config file parts like status server are only relevant in the context of the command line application, this can tell the cryptoassets framework how to set up itself. By default it initializes all the subsystems.
        """

        self.subsystems = subsystems

        #: SQLAlchemy database used engine
        self.engine = None

        #: cryptoassets.core.coin.registry.CoinRegistry instance
        self.coins = {}

        #: Dict of notify handlers
        self.notifiers = {}

        #: TODO: Make this more explicity?
        self.session = DBSession

        #: Configured status server
        #: See notes in cryptoassets.core.service.main.Service
        self.status_server = None

        #: The number of attempts we try to replay conflicted transactions. Set by configuration.
        self.transaction_retries = None

        #: cryptoassets.core.utils.conflictresolver.ConflictResolver instance we use to resolve database conflicts
        self.conflict_resolved = None

    def is_enabled(self, subsystem):
        """Are we running with a specific subsystem enabled."""
        return subsystem in self.subsystems

    def setup_session(self, transaction_retries=3):
        """Configure SQLAlchemy models and transaction conflict resolutoin.

        Also, bind created cryptocurrency models to their configured backends.
        """

        if not self.is_enabled(Subsystem.database):
            raise RuntimeError("Database subsystem was not enabled")

        self.Session = scoped_session(sessionmaker(autocommit=False, autoflush=False, bind=self.engine))

        self.conflict_resolver = ConflictResolver(self.open_session, self.transaction_retries)

        for name, coin in self.coins.all():
            coin.wallet_model.backend = coin.backend
            coin.address_model.backend = coin.backend
            coin.transaction_model.backend = coin.backend
            coin.account_model.backend = coin.backend

    def open_session(self):
        """Get new read-write session for the database."""
        return self.Session()

    def open_readonly_session(self):
        """Get new read-only access to database.

        This session can never write to db, so db can ignore transactions and optimize for speed.

        TODO
        """
        return self.session

    def create_tables(self):
        """Create database tables.

        Usually call only once when settings up the production database, or every time unit test case runs.
        """
        if not self.is_enabled(Subsystem.database):
            raise RuntimeError("Database subsystem was not enabled")

        Base.metadata.create_all(self.engine)
