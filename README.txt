cryptoassets
=============

.. contents:: :local:

A Python library for building Bitcoin and cryptocurrency service.

Features
-----------------

* Choose your favotire cryptocurrencies from the vast list or easily include your own coin

* Accounting: Make professional cryptocurrency services where pro forma statement can be generated

* Off-chain and internal transactions for building ecommerce, recurring payment and escrow sites

* Fault tolerant architecture, ACID transactions

* Vendor independent - allows you to use API services or run raw cryptocurrency protocol daemon

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

Supported backends
---------------------

* `block.io <https://block.io>`_

* `blockchain.info <http://blockchain.info>`_

* *bitcoind* and its derivates

Supported Python frameworks
----------------------------

* Pyramid

* Django

* Flask

... and all others Python application swhere `SQL Alchemy can be run <http://www.sqlalchemy.org/>`_

Getting Started
---------------

TODO

Running tests
--------------

Example::

    # Testnet API keys
    export BLOCK_IO_API_KEY="923f-e3e9-a580-dfb2"
    export BLOCK_IO_API_KEY_DOGE="0266-c2b6-c2c8-ee07"
    export BLOCK_IO_PIN="foobar123"
    export BLOCK_IO_TESTNET_TEST_FUND_ADDRESS="2MsgW3kCrRFtJuo9JNjkorWXaZSvLk4EWRr"
    export BLOCK_IO_DOGE_TESTNET_TEST_FUND_ADDRESS="2MxkkbbAwjT7pXme5766d6LUmKyZYEpDTMi"

    # block.io receiving transaction testing
    export PUSHER_API_KEY="e9f5cc20074501ca7395"

    # A real wallet, not testnet!
    export BLOCKCHAIN_IDENTIFIER="x"
    export BLOCKCHAIN_PASSWORD="y"

Running all tests::

    python setup.py test

Running a single test::

    python -m unittest cryptoassets.tests.test_block_io.BlockIoBTCTestCase.test_send_receive_external



