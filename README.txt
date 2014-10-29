cryptoassets
=============

.. contents:: :local:

A Python library for building Bitcoin and cryptocurrency service.
Provides Bitcoin, cryptocurrency and cryptoassets APIs, database models and accounting.

Features
-----------------

* Support your favorite cryptocurrency from the vast list, or easily extend to support your own coin

* Accounting: Make professional cryptocurrency services where pro forma bookkeeping reports can be generated

* Off-chain and internal transactions for building ecommerce, recurring payment and escrow sites

* Fault tolerant architecture, ACID transactions

* Built the scalability in mind - up to thousands of transactions per second

* Vendor independent - allows you to use API services or run raw cryptocurrency protocol daemon

* Test coverage > 90 %

Requirements
---------------

* Python 3

Depending on the cryptocurrency backend you wish to use you may need to install additional Python libraries.

Supported cryptocurrencies
----------------------------------

* Bitcoin

* Dogecoin

* Litecoin

Supported databases
----------------------------------

* PostgreSQL

* SQLite

* MySQL

* Oracle

`For the full list see SQLAlchemy dialects documentation <http://docs.sqlalchemy.org/en/rel_0_9/dialects/index.html>`_.

Supported backends
---------------------

``cryptocurrencies.core`` can operate on raw cryptocurrency server
daemon. Alternative you can choose one of the API services in the
case you do not have the server budget to run the full cryptocurrency node.

* `block.io <https://block.io>`_

* `blockchain.info <http://blockchain.info>`_

* *bitcoind* and its derivates

Supported Python frameworks
----------------------------

* Pyramid

* Django

* Flask

... and all others Python application swhere `SQLAlchemy can be run <http://www.sqlalchemy.org/>`_

Documentation
---------------

TODO

Getting Started
---------------

As the maturity of this project is very alpha, there aren't yet specific starting instructions.
You need to understand SQLAlchemy basics before you can start working on it.
However, as the project matures more comprehensive tutorials will follow.

For the examples, see ``test_block_io.py`` which stresses out Bitcoin and Dogecoin
using *block.io* backend.

**Walkthrough**

* Create an SQLAlchemy models in your database by importing your
  supported currencies from cryptoassets.core.coin and running `
  ``Base.metadata.create_all()``.

* Create a backend object and register it

* Get or create a default ``Wallet`` instance for your application

* Use ``Wallet`` to create account, then create address inside it

* Send in a transaction to this address

* You need to have external receiver process communicating with the network
  and then writing the transaction when it arrives (see ``test_send_receive_external``
  and ``setup_receiving``)

* Check that the address balance, account balance and wallet balances are updated



