"""Which database models to use with each currency.

Each cryptocurrency provides its own Wallet SQLAlchemy model.
Other models and database tables are derived from the wallet model.
"""
_wallet_models = {}


def register_wallet_model(coin, model):
    """Register a wallet model to be used for cryptocurrency management.

    :param coin: lowercase letter symbol for the cryptocurrency, like `btc` or `doge`.

    :param backend: Instance of :py:class:`cryptocurrency.core.backend.base.CoinBackend`.
    """
    assert type(coin) == str
    _wallet_models[coin.lower()] = model


def get_wallet_class(coin):
    """Get the SQL Alchemy model used as the wallet model for a coin.

    :param coin: lowercase letter symbol for the cryptocurrency, like `btc` or `doge`.

    :return: GenericWallet subclass
    """
    return _wallet_models[coin]


def get_address_class(coin):
    """Get the SQL Alchemy model used as the address model for a coin.

    :param coin: lowercase letter symbol for the cryptocurrency, like `btc` or `doge`.

    :return: GenericAddress subclass
    """
    return _wallet_models[coin].Address
