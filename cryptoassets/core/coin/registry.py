"""Which database models to use with each currency.

Each cryptocurrency provides its own Wallet SQLAlchemy model.
Other models and database tables are derived from the wallet model.
"""


class Coin:
    """Cryptocurrency setup entry.

    Bind cryptocurrency to its backend and database models.
    """

    def __init__(self, wallet_model):
        self.wallet_model = wallet_model

        #: Set later to avoid circular referencies when constructing backend
        self.backend = None

    @property
    def address_model(self):
        return self.wallet_model.Address

    @property
    def transaction_model(self):
        return self.wallet_model.Transaction

    @property
    def account_model(self):
        return self.wallet_model.Account


class CoinRegistry:
    """Hold data of set up cryptocurrencies."""

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
        return self.coins.get(name)
