"""Cryptoassets application manager."""

from .models import DBSession
from .models import Base

from .utils import AutoNumber


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

    #: Post notifications
    notifiers = ()


ALL_SUBSYSTEMS = Subsystem.__members__.values()


class CryptoAssetsApp:
    """This class ties all strings together to make a runnable cryptoassets app."""

    def __init__(self, subsystems):
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

    def is_enabled(self, subsystem):
        """Are we running with a specific subsystem enabled."""
        return subsystem in self.subsystems

    def setup_session(self):
        """Configure SQLAlchemy models.

        Also bind created cryptocurrency models to their backend.
        """

        if not self.is_enabled(Subsystem.database):
            raise RuntimeError("Database subsystem was not enabled")

        self.session.configure(bind=self.engine)

        for name, coin in self.coins.all():
            coin.wallet_model.backend = coin.backend
            coin.address_model.backend = coin.backend
            coin.transaction_model.backend = coin.backend
            coin.account_model.backend = coin.backend

    def create_tables(self):
        """Create database tables.

        Usually call only once when settings up the production database, or every time unit test case runs.
        """
        if not self.is_enabled(Subsystem.database):
            raise RuntimeError("Database subsystem was not enabled")

        Base.metadata.create_all(self.engine)
