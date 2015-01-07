"""All running cryptoassets are maintained in a coin registry.

Each cryptoasset provides its own Wallet SQLAlchemy model and backend instance which is used to communicate with the network of the cryptoasset.
"""
from zope.dottedname.resolve import resolve


class CoinModelDescription:
    """Describe cryptocurrency data structures: what SQLAlchemy models and database classes it uses.

    """

    #: Name of this coin
    coin_name = None

    # Direct model class reference. Available after Python modules are loaded and Cryptoassets App session initialized
    _Wallet = None
    _Address = None
    _Account = None
    _NetworkTransaction = None
    _Transaction = None

    def __init__(self, coin_name, wallet_model_name, address_model_name, account_model_name, transaction_model_name, network_transaction_model_name):
        self.coin_name = coin_name
        self.wallet_model_name = wallet_model_name
        self.address_model_name = address_model_name
        self.account_model_name = account_model_name
        self.transaction_model_name = transaction_model_name
        self.network_transaction_model_name = network_transaction_model_name

    @property
    def Wallet(self):
        return self._lazy_initialize_class_ref("_Wallet", self.wallet_model_name)

    @property
    def Address(self):
        return self._lazy_initialize_class_ref("_Address", self.address_model_name)

    @property
    def Account(self):
        return self._lazy_initialize_class_ref("_Account", self.account_model_name)

    @property
    def NetworkTransaction(self):
        return self._lazy_initialize_class_ref("_NetworkTransaction", self.network_transaction_model_name)

    @property
    def Transaction(self):
        return self._lazy_initialize_class_ref("_Transaction", self.transaction_model_name)

    @property
    def wallet_table_name(self):
        return "{}_wallet".format(self.coin_name)

    @property
    def account_table_name(self):
        return "{}_account".format(self.coin_name)

    @property
    def address_table_name(self):
        return "{}_address".format(self.coin_name)

    @property
    def transaction_table_name(self):
        return "{}_transaction".format(self.coin_name)

    @property
    def network_transaction_table_name(self):
        return "{}_network_transaction".format(self.coin_name)

    def _lazy_initialize_class_ref(self, name, dotted_name):
        val = getattr(self, name, None)
        if val:
            return val
        else:
            val = resolve(dotted_name)
            setattr(self, name, val)
        return val


class Coin:
    """Describe one cryptocurrency setup.

    Binds cryptocurrency to its backend and database models.
    """

    def __init__(self, coin_description, backend=None):

        assert isinstance(coin_description, CoinModelDescription)

        self.coin_description = coin_description

        #: Subclass of :py:class:`cryptoassets.core.backend.base.CoinBackend`.
        self.backend = None

        #: Lowercase acronym name of this asset
        self.name = None

    @property
    def address_model(self):
        """SQLAlchemy model for address of this cryptoasset.

        Subclass of :py:class:`cryptoassets.core.models.GenericAddress`.
        """
        return self.coin_description.Address

    @property
    def transaction_model(self):
        """SQLAlchemy model for transaction of this cryptoasset.

        Subclass of :py:class:`cryptoassets.core.models.GenericTransaction`.
        """
        return self.coin_description.Transaction

    @property
    def account_model(self):
        """SQLAlchemy model for account of this cryptoasset.

        Subclass of :py:class:`cryptoassets.core.models.GenericAccount`.
        """
        return self.coin_description.Account

    @property
    def wallet_model(self):
        """SQLAlchemy model for account of this cryptoasset.

        Subclass of :py:class:`cryptoassets.core.models.GenericWallet`.
        """
        return self.coin_description.Wallet

    @property
    def network_transaction_model(self):
        """SQLAlchemy model for account of this cryptoasset.

        Subclass of :py:class:`cryptoassets.core.models.GenericWallet`.
        """
        return self.coin_description.NetworkTransaction


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
