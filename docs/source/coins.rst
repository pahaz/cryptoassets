================================
Cryptocurrency and asset support
================================

.. contents:: :local:

Introduction
--------------

``cryptoassets.core`` supports different cryptocurrencies. We use `SQLAlchemy <http://www.sqlalchemy.org/>`_ to generate a set of database tables and model classes for each coin. Then this coin can be send and received using a :doc:`backend <./backends>` which takes care of communicating with the underlying cryptocurrency network.

cryptoassets.core.coin.bitcoin
---------------------------------


.. automodule:: cryptoassets.core.coin.bitcoin.models
    :members:

cryptoassets.core.coin.dogecoin
--------------------------------

.. automodule:: cryptoassets.core.coin.dogecoin.models
    :members: