"""Non-functional cryptocurrency backend doing nothing. Use for testing purposes.

The backend configuration takes following parameters.

:param class: Always ``cryptoassets.core.backend.null.DummyCoinBackend``
"""

import random
from decimal import Decimal

from . import base


class DummyCoinBackend(base.CoinBackend):

    def __init__(self, coin):
        self.coin = coin

    def create_address(self, label):
        return "foobar{}".format(random.randint(0, 999999))

    def get_backend_balance(self):
        """In the country of null, we always have balance!"""
        return Decimal(999999)

    def get_balances(self, addresses):
        pass

    def send(self, recipients):
        pass

    def scan_addresses(addresses):
        raise RuntimeError("Not supported")

    def setup_incoming_transactions(self, dbsession):
        pass

    def require_tracking_incoming_confirmations(self):
        return False

    def list_received_transactions(self, extra={}):
        raise NotImplementedError()
