"""Cryptoassets application manager."""

from .models import DBSession
from .models import Base


class CryptoAssetsApp:
    """This class ties all strings together to make a runnable cryptoassets app."""

    def __init__(self):

        #: SQLAlchemy database used engine
        self.engine = None

        #: cryptoassets.core.coin.registry.CoinRegistry instance
        self.coins = {}

        #: Dict of notify handlers
        self.notifiers = {}

        #: TODO: Make this more explicity?
        self.session = DBSession

        #: Configured status server
        self.status_server = None

    def setup_session(self):
        """Configure SQLAlchemy models."""
        self.session.configure(bind=self.engine)

    def create_tables(self):
        Base.metadata.create_all(self.engine)
