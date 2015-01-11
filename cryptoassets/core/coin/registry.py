"""All running cryptoassets are maintained in a coin registry.

Each cryptoasset provides its own Wallet SQLAlchemy model and backend instance which is used to communicate with the network of the cryptoasset.
"""
from zope.dottedname.resolve import resolve


class CoinModelDescription:
    """Describe one cryptocurrency data structures: what SQLAlchemy models and database tables it uses.

    The instance of this class is used by :py:class:`cryptoassets.core.models.CoinDescriptionModel` to build the model relatinoships and foreign keys between the tables of one cryptoasset.
    """

    def __init__(self, coin_name, wallet_model_name, address_model_name, account_model_name, transaction_model_name, network_transaction_model_name, address_validator):
        """Create the description with fully dotted paths to Python classes.

        :param coin_name: Name of this coin, lowercase acronym
        """
        assert coin_name == coin_name.lower()

        self.coin_name = coin_name
        self.wallet_model_name = wallet_model_name
        self.address_model_name = address_model_name
        self.account_model_name = account_model_name
        self.transaction_model_name = transaction_model_name
        self.network_transaction_model_name = network_transaction_model_name
        self.address_validator = address_validator

        # Direct model class reference. Available after Python modules are loaded and Cryptoassets App session initialized
        self._Wallet = None
        self._Address = None
        self._Account = None
        self._NetworkTransaction = None
        self._Transaction = None

    @property
    def Wallet(self):
        """Get wallet model class."""
        return self._lazy_initialize_class_ref("_Wallet", self.wallet_model_name)

    @property
    def Address(self):
        """Get address model class."""
        return self._lazy_initialize_class_ref("_Address", self.address_model_name)

    @property
    def Account(self):
        """Get account model class."""
        return self._lazy_initialize_class_ref("_Account", self.account_model_name)

    @property
    def NetworkTransaction(self):
        """Get network transaction model class."""
        return self._lazy_initialize_class_ref("_NetworkTransaction", self.network_transaction_model_name)

    @property
    def Transaction(self):
        """Get transaction model class."""
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

    We also carry a flag if we are running in testnet or not. This affects address validation.
    """

    def __init__(self, coin_description, backend=None, max_confirmation_count=15, testnet=False):
        """Create a binding between asset models and backend.

        :param coin_description: :py:class:`cryptoassets.core.coin.registry.CoinModelDescription`

        :param testnet: Are we running a testnet node or real node.

        :param backend: :py:class:`cryptoassets.core.backend.base.CoinBackend`
        """

        assert isinstance(coin_description, CoinModelDescription)

        self.coin_description = coin_description

        #: Subclass of :py:class:`cryptoassets.core.backend.base.CoinBackend`.
        self.backend = None

        #: Lowercase acronym name of this asset
        self.name = None

        #: This is how many confirmations ``tools.confirmationupdate`` tracks for each network transactions, both incoming and outgoing, until we consider it "closed" and stop polling backend for updates.
        self.max_confirmation_count = max_confirmation_count

        self.testnet = testnet

    @property
    def address_model(self):
        """Property to get SQLAlchemy model for address of this cryptoasset.

        Subclass of :py:class:`cryptoassets.core.models.GenericAddress`.
        """
        return self.coin_description.Address

    @property
    def transaction_model(self):
        """Property to get SQLAlchemy model for transaction of this cryptoasset.

        Subclass of :py:class:`cryptoassets.core.models.GenericTransaction`.
        """
        return self.coin_description.Transaction

    @property
    def account_model(self):
        """Property to get SQLAlchemy model for account of this cryptoasset.

        Subclass of :py:class:`cryptoassets.core.models.GenericAccount`.
        """
        return self.coin_description.Account

    @property
    def wallet_model(self):
        """Property to get SQLAlchemy model for account of this cryptoasset.

        Subclass of :py:class:`cryptoassets.core.models.GenericWallet`.
        """
        return self.coin_description.Wallet

    @property
    def network_transaction_model(self):
        """Property to get SQLAlchemy model for account of this cryptoasset.

        Subclass of :py:class:`cryptoassets.core.models.GenericWallet`.
        """
        return self.coin_description.NetworkTransaction

    def validate_address(self, address):
        """Check the address validy against current network.

        :return: True if given address is valid.
        """
        return self.coin_description.address_validator.validate_address(address, self.testnet)


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
