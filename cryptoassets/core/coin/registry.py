"""Which database models to use with each currency.

Each cryptocurrency provides its own Wallet SQLAlchemy model.
Other models and database tables are derived from the wallet model.
"""

class Coin:
    """Cryptocurrenct configuration entry."""

    def __init__(self, wallet_model, backend):
        self.wallet_model = wallet_model
        self.backend = backend


class CoinRegistry:

    def __init__(self):
        self.coins = {}

    def register(self, name, coin):
        self.coins[name] = coin

    def all(self):
        """Get all registered coin models.

        :return: List of coin names
        """
        return self.coins.keys()

    def get(self, name):
        return self.coins.get(name)
