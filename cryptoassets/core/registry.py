"""Bindings between database models and backend used for the cryptocurrency transactions.
"""
_backends = {}


def register(coin, backend):
    """Register a backend instance to be used for cryptocurrency management.

    :param coin: lowercase letter symbol for the cryptocurrency, like `btc` or `doge`.

    :param backend: Instance of :py:class:`cryptocurrency.core.backend.base.CoinBackend`.
    """
    assert type(coin) == str
    _backends[coin.lower()] = backend


def get(coin):
    return _backends[coin]
