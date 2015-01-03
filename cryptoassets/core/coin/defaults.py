"""Default cryptocurrency names and their models."""

#: This is the default mapping between the three-letter coin acronyms and their SQLAlchemy model presentations. If you want to use your own database models you can override any of these in your configuration.
COIN_MODEL_DEFAULTS = {
    "btc": "cryptoassets.core.coin.bitcoin.models",
    "ltc": "cryptoassets.core.coin.litecoin.models",
    "doge": "cryptoassets.core.coin.dogecoin.models",
    "aby": "cryptoassets.core.coin.applebyte.models",
}
