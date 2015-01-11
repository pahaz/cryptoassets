"""AppleByte database support."""

from cryptoassets.core import models
from cryptoassets.core.coin.registry import CoinModelDescription
from cryptoassets.core.coin.validate import HashAddresValidator

coin_description = CoinModelDescription(
    coin_name="aby",
    wallet_model_name="cryptoassets.core.coin.applebyte.models.AppleByteWallet",
    address_model_name="cryptoassets.core.coin.applebyte.models.AppleByteAddress",
    account_model_name="cryptoassets.core.coin.applebyte.models.AppleByteAccount",
    transaction_model_name="cryptoassets.core.coin.applebyte.models.AppleByteTransaction",
    network_transaction_model_name="cryptoassets.core.coin.applebyte.models.AppleByteNetworkTransaction",
    address_validator=HashAddresValidator())


class AppleByteAccount(models.GenericAccount):
    coin_description = coin_description


class AppleByteAddress(models.GenericAddress):
    coin_description = coin_description


class AppleByteTransaction(models.GenericConfirmationTransaction):
    coin_description = coin_description


class AppleByteWallet(models.GenericWallet):
    coin_description = coin_description


class AppleByteNetworkTransaction(models.GenericConfirmationNetworkTransaction):
    coin_description = coin_description
