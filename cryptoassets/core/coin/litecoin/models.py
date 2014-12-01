"""Litecoin database implementation.

All amounts are stored in satoshis in integer fields.

Modify ``LitecoinTransaction.confirmation_count`` global
to set the threshold when transcations are considered confirmed.
"""
from cryptoassets.core import models


class LitecoinAccount(models.GenericAccount):
    coin = "ltc"
    _wallet_cls_name = "LitecoinWallet"
    _address_cls_name = "LitecoinAddress"


class LitecoinAddress(models.GenericAddress):
    coin = "ltc"
    _account_cls_name = "LitecoinAccount"


class LitecoinTransaction(models.GenericConfirmationTransaction):
    coin = "ltc"
    _wallet_cls_name = "LitecoinWallet"
    _account_cls_name = "LitecoinAccount"
    _address_cls_name = "LitecoinAddress"


class LitecoinWallet(models.GenericWallet):
    coin = "ltc"
    Address = LitecoinAddress
    Account = LitecoinAccount
    Transaction = LitecoinTransaction