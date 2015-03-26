==========================================
Application and API service support
==========================================

.. contents:: :local:

Introduction
===============

*cryptoassets.core* can operate on raw cryptocurrency server daemon. Alternative you can choose one of the API services in the case you do not have the budget to run the full cryptocurrency node.

One instance of *cryptoassets.core* supports multiple backends. E.g. you can run application doing both Bitcoin and Dogecoin at the same time. However one backend can be enabled for one cryptoasset at a time.

After the backend has been set up you rarely interact it with directly. Instead, you use :doc:`model APIs <api/models>` and :doc:`cryptoassets helper service <./service>` takes care of cryptoassets operations.

Running your cryptocurrency daemon (bitcoind)
--------------------------------------------------------

Pros

* You have 100% control of assets

* You are not dependend of any vendor (downtime, asset seizure)

Cons

* Running *bitcoind* requires root server access, 2 GB of RAM and 25 GB of disk space minimum and cannot be done on low budget web hosting accounts

* You need to have sysadmin skills and be aware of server security

Using API service
----------------------------

Pros

* Easy to set up

* Works with even low budget hosting

Cons

* Increases attack surface

* If the service provider goes out of business you might lose your hot wallet assets

Configuration
===============

The backend is configured separate for each cryptocurrency (BTC, Doge) and registered in :py:mod:`cryptoassets.backend.registry`. Each backend takes different initialization arguments like API keys and passwords. You usually set up these in :doc:`cryptoassets.core config <./config>`.

The active backend configuration can be read through :py:class:`cryptoassets.core.coin.registry.CoinRegistry`. Bindings between the backends and the cryptocurrenct are described  by :py:class:`cryptoassets.core.coin.registry.Coin` class.

Backends
==============================

bitcoind
--------------

.. automodule:: cryptoassets.core.backend.bitcoind

Wallet notifications
+++++++++++++++++++++++++++++++++++++++++++++++++

Wallet notifications (or, short, ``walletnotify``) is the term used by *cryptoasset.core* to describe how backend communicates back to :doc:`cryptoassets helper service <./service>`. It's named after *bitcoind* `walletnotify <https://en.bitcoin.it/wiki/Running_Bitcoin#Bitcoin.conf_Configuration_File>`_ option.

* You can setup different wallet notify method depending if you run daemon application locally, on a remote server or you use some API service

* In theory, you could mix and match backends and wallet notifications methods. But just stick to what is recommended for the backend recommends.

* Each cryptoasset require its own notification channel (named pipe, HTTP server port)

HTTP webhook for bitcoind
+++++++++++++++++++++++++++++++++++++++++++++++++

.. automodule:: cryptoassets.core.backend.httpwalletnotify

Named UNIX pipe for bitcoind
+++++++++++++++++++++++++++++++++++++++++++++++++

.. automodule:: cryptoassets.core.backend.pipewalletnotify

Redis pubsub for bitcoind
+++++++++++++++++++++++++++++++++++++++++++++++++

.. automodule:: cryptoassets.core.backend.rediswalletnotify

block.io
--------------

.. automodule:: cryptoassets.core.backend.blockio

Wallet notifications over websockets
+++++++++++++++++++++++++++++++++++++++++++++++++

.. automodule:: cryptoassets.core.backend.blockiowebsocket

Wallet notifications over web hooks (HTTP)
++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

.. automodule:: cryptoassets.core.backend.blockiowebhook

blockchain.info
-----------------

.. automodule:: cryptoassets.core.backend.blockchain

null
-----------------

.. automodule:: cryptoassets.core.backend.null

