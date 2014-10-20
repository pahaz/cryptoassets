from cryptoassets import models


class BitcoinAccount(models.GenericAccount):
    coin = "btc"
    pass


class BitcoinAddress(models.GenericAddress):
    coin = "btc"
    pass


class BitcoinTransaction(models.GenericConfirmationTransaction):
    coin = "btc"
    pass


class BitcoinWallet(models.GenericWallet):
    coin = "btc"
    Address = BitcoinAddress
    Account = BitcoinAccount
    Transaction = BitcoinTransaction