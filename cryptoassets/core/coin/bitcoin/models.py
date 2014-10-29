"""Bitcoin database implementation.

All amounts are stored in satoshis in integer fields.

Modify ``BitcoinTransaction.confirmation_count`` global
to set the threshold when transcations are considered confirmed.
"""
from cryptoassets.core import models


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
