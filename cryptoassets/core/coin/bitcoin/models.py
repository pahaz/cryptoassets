"""Bitcoin database implementation.

All amounts are stored in satoshis in integer fields.

Modify ``BitcoinTransaction.confirmation_count`` global
to set the threshold when transcations are considered confirmed.
"""
from cryptoassets.core import models
from cryptoassets.core.coin.registry import CoinModelDescription
from cryptoassets.core.coin.validate import HashAddresValidator


coin_description = CoinModelDescription(
    coin_name="btc",
    wallet_model_name="cryptoassets.core.coin.bitcoin.models.BitcoinWallet",
    address_model_name="cryptoassets.core.coin.bitcoin.models.BitcoinAddress",
    account_model_name="cryptoassets.core.coin.bitcoin.models.BitcoinAccount",
    transaction_model_name="cryptoassets.core.coin.bitcoin.models.BitcoinTransaction",
    network_transaction_model_name="cryptoassets.core.coin.bitcoin.models.BitcoinNetworkTransaction",
    address_validator=HashAddresValidator())


class BitcoinAccount(models.GenericAccount):
    coin_description = coin_description


class BitcoinAddress(models.GenericAddress):
    coin_description = coin_description


class BitcoinTransaction(models.GenericConfirmationTransaction):
    coin_description = coin_description


class BitcoinWallet(models.GenericWallet):
    coin_description = coin_description


class BitcoinNetworkTransaction(models.GenericConfirmationNetworkTransaction):
    coin_description = coin_description
