"""Dogecoin database support."""

from cryptoassets.core import models


class DogeAccount(models.GenericAccount):
    coin = "doge"
    _wallet_cls_name = "DogeWallet"
    _address_cls_name = "DogeAddress"


class DogeAddress(models.GenericAddress):
    coin = "doge"
    _account_cls_name = "DogeAccount"


class DogeTransaction(models.GenericConfirmationTransaction):
    coin = "doge"
    _wallet_cls_name = "DogeWallet"
    _account_cls_name = "DogeAccount"
    _address_cls_name = "DogeAddress"


class DogeWallet(models.GenericWallet):
    coin = "doge"
    Address = DogeAddress
    Account = DogeAccount
    Transaction = DogeTransaction
