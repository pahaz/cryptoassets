
_backends = {}


def register(coin, backend):
    _backends[coin] = backend


def get(coin):
    return _backends[coin]
