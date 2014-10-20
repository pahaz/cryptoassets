from cryptoassets import models


class DogeAccount(models.GenericAccount):
    coin = "doge"
    pass


class DogeAddress(models.GenericAddress):
    coin = "doge"
    pass


class DogeTransaction(models.GenericConfirmationTransaction):
    coin = "doge"
    pass


class DogeWallet(models.GenericWallet):
    coin = "doge"
    Address = DogeAddress
    Account = DogeAccount
    Transaction = DogeTransaction
