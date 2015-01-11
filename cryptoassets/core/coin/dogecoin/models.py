"""Dogecoin database support."""

from cryptoassets.core import models
from cryptoassets.core.coin.registry import CoinModelDescription
from cryptoassets.core.coin.validate import HashAddresValidator

coin_description = CoinModelDescription(
    coin_name="doge",
    wallet_model_name="cryptoassets.core.coin.dogecoin.models.DogecoinWallet",
    address_model_name="cryptoassets.core.coin.dogecoin.models.DogecoinAddress",
    account_model_name="cryptoassets.core.coin.dogecoin.models.DogecoinAccount",
    transaction_model_name="cryptoassets.core.coin.dogecoin.models.DogecoinTransaction",
    network_transaction_model_name="cryptoassets.core.coin.dogecoin.models.DogecoinNetworkTransaction",
    address_validator=HashAddresValidator())


class DogecoinAccount(models.GenericAccount):
    coin_description = coin_description


class DogecoinAddress(models.GenericAddress):
    coin_description = coin_description


class DogecoinTransaction(models.GenericConfirmationTransaction):
    coin_description = coin_description


class DogecoinWallet(models.GenericWallet):
    coin_description = coin_description


class DogecoinNetworkTransaction(models.GenericConfirmationNetworkTransaction):
    coin_description = coin_description
