"""All running cryptoassets are maintained in a coin registry.

Each cryptoasset provides its own Wallet SQLAlchemy model and backend instance which is used to communicate with the network of the cryptoasset.
"""


class Coin:
    """Describe one cryptocurrency setup.

    Binds cryptocurrency to its backend and database models.
    """

    def __init__(self, wallet_model):
        self._wallet_model = wallet_model

        #: Subclass of :py:class:`cryptoassets.core.backend.base.CoinBackend`.
        self.backend = None

        #: Lowercase acronym name of this asset
        self.name = None

    @property
    def address_model(self):
        """SQLAlchemy model for address of this cryptoasset.

        Subclass of :py:class:`cryptoassets.core.models.GenericAddress`.
        """
        return self._wallet_model.Address

    @property
    def transaction_model(self):
        """SQLAlchemy model for transaction of this cryptoasset.

        Subclass of :py:class:`cryptoassets.core.models.GenericTransaction`.
        """
        return self._wallet_model.Transaction

    @property
    def account_model(self):
        """SQLAlchemy model for account of this cryptoasset.

        Subclass of :py:class:`cryptoassets.core.models.GenericAccount`.
        """
        return self._wallet_model.Account

    @property
    def wallet_model(self):
        """SQLAlchemy model for account of this cryptoasset.

        Subclass of :py:class:`cryptoassets.core.models.GenericWallet`.
        """
        return self._wallet_model


class CoinRegistry:
    """Holds data of set up cryptocurrencies.

    Usually you access this through :py:attr:`cryptoasssets.core.app.CryptoassetsApp.coins` instance.

    Example::

        cryptoassets_app = CryptoassetsApp()
        # ... setup ...

        bitcoin = cryptoassets_app.coins.get("btc)

        print("We are running bitcoin with backend {}".format(bitcoin.backend))

    """

    def __init__(self):
        self.coins = {}

    def register(self, name, coin):
        self.coins[name] = coin
        # Setup backref
        coin.name = name

    def all(self):
        """Get all registered coin models.

        :return: List of tuples(coin name, Coin)
        """
        return self.coins.items()

    def get(self, name):
        """Return coin setup data by its acronym name.

        :param name: All lowercase, e.g. ``btc``.
        """
        return self.coins.get(name)
