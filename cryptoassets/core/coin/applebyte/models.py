"""AppleByte database implementation.

All amounts are stored in satoshis in integer fields.

Modify ``AppleByteTransaction.confirmation_count`` global
to set the threshold when transcations are considered confirmed.
"""
from cryptoassets.core import models


class AppleByteAccount(models.GenericAccount):
    coin = "aby"
    _wallet_cls_name = "AppleByteWallet"
    _address_cls_name = "AppleByteAddress"


class AppleByteAddress(models.GenericAddress):
    coin = "aby"
    _account_cls_name = "AppleByteAccount"


class AppleByteTransaction(models.GenericConfirmationTransaction):
    coin = "aby"
    _wallet_cls_name = "AppleByteWallet"
    _account_cls_name = "AppleByteAccount"
    _address_cls_name = "AppleByteAddress"


class AppleByteWallet(models.GenericWallet):
    coin = "aby"
    Address = AppleByteAddress
    Account = AppleByteAccount
    Transaction = AppleByteTransaction
