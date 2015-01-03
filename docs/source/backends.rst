==========================================
Daemons and API services support
==========================================

.. contents:: :local:

Introduction
--------------

*cryptoassets.core* can operate on raw cryptocurrency server daemon. Alternative you can choose one of the API services in the case you do not have the server budget to run the full cryptocurrency node. Each backend implements :py:mod:`cryptocurrency.core.backend.base.CoinBackend`
functionality.

The backend is configured separate for each cryptocurrency (BTC, Doge) and registered in :py:mod:`cryptoassets.backend.registry`. The backend creatoin may take different parameters like API keys and passwords.

Because operations in the backend are potentially blocking for a longer period, all operations here are meant to execute from a separate asynchronous process which manages sending/receiving.

Bindings between the backends and the cryptocurrenct are managed by :py:mod:`cryptoassets.core.base.CoinBackend`. When you call the model API, the calls are delegated to the currently configured backend through :py:mod:`cryptoassets.core.coin.registry`.

bitcoind
--------------

.. automodule:: cryptoassets.core.backend.bitcoind

block.io
--------------

.. automodule:: cryptoassets.core.backend.blockio

blockchain.info
-----------------

.. automodule:: cryptoassets.core.backend.blockchain

null
-----------------

.. automodule:: cryptoassets.core.backend.null

