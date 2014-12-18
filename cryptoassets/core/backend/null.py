from . import base


class DummyCoinBackend(base.CoinBackend):
    """Dummy cryptocurrency backend doing nothing for testing purposes."""

    def __init__(self, coin):
        self.coin = coin

    def create_address(self, label):
        pass

    def get_backend_balance(self):
        return Decimal(999999)

    def get_balances(self, addresses):
        pass

    def get_lock(self, name):
        pass

    def send(self, recipients):
        pass

    def scan_addresses(addresses):
        raise RuntimeError("Not supported")

    def setup_incoming_transactions(self, dbsession):
        pass
