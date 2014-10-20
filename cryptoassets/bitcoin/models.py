from .. import models


class BitcoinAccount(models.GenericAccount):
    coin = "btc"
    pass


class BitcoinWallet(models.GenericWallet):
    coin = "btc"
    pass

    def _create_address(self):
        return BitcoinAddress()

    def _create_account(self):
        return BitcoinAccount()

    def _create_transaction(self):
        return BitcoinTransaction()


class BitcoinAddress(models.GenericAddress):
    coin = "btc"
    pass


class BitcoinTransaction(models.GenericConfirmationTransaction):
    coin = "btc"
    pass
