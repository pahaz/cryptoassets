================================
Cryptocurrency and asset support
================================

.. contents:: :local:

Introduction
--------------

``cryptoassets.core`` supports different cryptocurrencies. We use `SQLAlchemy <http://www.sqlalchemy.org/>`_ to generate a set of database tables and model classes for each coin. Then this coin can be send and received using a :doc:`backend <./backends>` which takes care of communicating with the underlying cryptocurrency network.

:doc:`See how to add support for more cryptocurrencies <./extend>`.

Bitcoin
---------------------------------

Supported backends:

* bitcoind

* block.io

* blockchain.info

`More info about Bitcoin <http://bitcoin.it/>`_.

.. automodule:: cryptoassets.core.coin.bitcoin.models
    :members:

Dogecoin
--------------------------------

`More info about Dogecoin <http://dogecoin.com/>`_.

Supported backends:

* dogecoind (bitcoind-like)

* block.io

.. automodule:: cryptoassets.core.coin.dogecoin.models
    :members:

AppleByte
--------------------------------

`More info about AppleByte <http://applebyte.me/>`_.

Supported backends:

* applebyted (bitcoind-like)

.. automodule:: cryptoassets.core.coin.dogecoin.models
    :members: