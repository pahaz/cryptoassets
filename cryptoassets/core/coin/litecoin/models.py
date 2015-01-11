"""Litecoin database support."""

from cryptoassets.core import models
from cryptoassets.core.coin.registry import CoinModelDescription
from cryptoassets.core.coin.validate import HashAddresValidator

coin_description = CoinModelDescription(
    coin_name="ltc",
    wallet_model_name="cryptoassets.core.coin.litecoin.models.LitecoinWallet",
    address_model_name="cryptoassets.core.coin.litecoin.models.LitecoinAddress",
    account_model_name="cryptoassets.core.coin.litecoin.models.LitecoinAccount",
    transaction_model_name="cryptoassets.core.coin.litecoin.models.LitecoinTransaction",
    network_transaction_model_name="cryptoassets.core.coin.litecoin.models.LitecoinNetworkTransaction",
    address_validator=HashAddresValidator())


class LitecoinAccount(models.GenericAccount):
    coin_description = coin_description


class LitecoinAddress(models.GenericAddress):
    coin_description = coin_description


class LitecoinTransaction(models.GenericConfirmationTransaction):
    coin_description = coin_description


class LitecoinWallet(models.GenericWallet):
    coin_description = coin_description


class LitecoinNetworkTransaction(models.GenericConfirmationNetworkTransaction):
    coin_description = coin_description
