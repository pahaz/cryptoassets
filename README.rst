cryptoassets.core
==================

.. image:: https://drone.io/bitbucket.org/miohtama/cryptoassets/status.png
    :target: https://drone.io/bitbucket.org/miohtama/cryptoassets/latest

.. image:: https://readthedocs.org/projects/cryptoassetscore/?badge=latest
    :target: http://cryptoassetscore.readthedocs.org/en/latest/

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

Supported environments
------------------------

Cryptocurrencies
++++++++++++++++++++

* Bitcoin

* Dogecoin

* Litecoin

Databases
++++++++++++++++++++

* PostgreSQL

* SQLite

* MySQL

* Oracle

`For the full list see SQLAlchemy dialects documentation <http://docs.sqlalchemy.org/en/rel_0_9/dialects/index.html>`_.

Protocols, daemons and API services
++++++++++++++++++++++++++++++++++++++

``cryptocurrencies.core`` can operate on raw cryptocurrency server
daemon. Alternative you can choose one of the API services in the
case you do not have the server budget to run the full cryptocurrency node.

* `block.io <https://block.io>`_

* `blockchain.info <http://blockchain.info>`_

* *bitcoind* and its derivates

Python frameworks
++++++++++++++++++++

* Pyramid

* Django

* Flask

... and all others Python application swhere `SQLAlchemy can be run <http://www.sqlalchemy.org/>`_

Documentation
---------------

`The documentation is on readthedocs.org <http://cryptoassetscore.readthedocs.org/en/latest/>`_.

Quick code samples
-------------------

An offchain transaction example::

    from cryptoassets.core.coin.bitcoin.models import BitcoinWallet

    wallet = BitcoinWallet()
    DBSession.add(wallet)
    # DBSession.flush() creates primary keys, so that
    # accounts can refer to this wallet object.
    DBSession.flush()

    sending_account = wallet.create_account("Test account")
    receiving_account = wallet.create_account("Test account 2")
    DBSession.flush()

    sending_account.balance = 100
    tx = wallet.send_internal(sending_account, receiving_account, 100, "Test transaction")

    print("Created internal transaction {}".format(tx))

A full transaction example::

    from cryptoassets.core.coin.bitcoin.models import BitcoinWallet
    from cryptoassets.backend.blockio import BlockIo

    # Construct a block.io API
    self.backend = BlockIo("btc", "My block.io API key", "My Block.io pin")
    backendregistry.register("btc", self.backend)

    wallet = BitcoinWallet()
    DBSession.add(wallet)
    DBSession.flush()

    # Create an account which cointains some balance for outgoing send
    from_account = wallet.create_account("Test sending account")
    DBSession.flush()

    # We have previously send some BTC TESNET sample coins to the block.io
    # wallet for the testing purposes
    wallet.add_address(account, "Sample imported address", \
        "2MsgW3kCrRFtJuo9JNjkorWXaZSvLk4EWRx")

    # Syncs the account balance with the network
    wallet.refresh_account_balance(from_account)

    # Send Bitcoins through blockchain, amount as satoshis
    wallet.send_external(from_account, "2MsgW3kCrRFtJuo9JNjkorWXaZSvLk4EWRx", 2200, \
        "Test send"))




