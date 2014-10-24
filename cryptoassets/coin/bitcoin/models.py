from cryptoassets import models


class BitcoinAccount(models.GenericAccount):
    coin = "btc"
    _wallet_cls_name = "BitcoinWallet"
    _address_cls_name = "BitcoinAddress"


class BitcoinAddress(models.GenericAddress):
    coin = "btc"
    _account_cls_name = "BitcoinAccount"


class BitcoinTransaction(models.GenericConfirmationTransaction):
    coin = "btc"
    _wallet_cls_name = "BitcoinWallet"
    _account_cls_name = "BitcoinAccount"
    _address_cls_name = "BitcoinAddress"


class BitcoinWallet(models.GenericWallet):
    coin = "btc"
    Address = BitcoinAddress
    Account = BitcoinAccount
    Transaction = BitcoinTransaction
