================================
Getting started
================================

.. contents:: :local:

Introduction
==============

*cryptoassets.core* provides safe, scalable and future-proof cryptocurrency and cryptoassets management for your Python application. You can use the framework to accept cryptocurrency payments, build cryptoasset services and exchanges.

Basics
======

* You can use *cryptoassets.core* framework in any Python application, including Django applications. Python 3 is required.

* *cryptoassets.core* support various cryptocurrencies and assets and is easily to extend support your favorite altcoint

* *cryptoassets.core* works with API services (block.io, blockchain.info) and daemons (*bitcoind*, *dogecoind*). You either to sign up for an account on any the API services or run the daemon on your own server. Please note that running *bitcoind* requires at least 2 GB of RAM and 20 GB of disk space.

* :doc`For data integrity reasons <./integrity>`, *cryptoassets.core* uses its own database connection which most likely will be different from your the normal database connection of your application.

* Some very basic `SQLAlchemy <http://www.sqlalchemy.org/>`_ knowledge is required for using the models API.

* You need to run a separate a :doc:`cryptoassets helper service <./service>` process which is responsible for communicating between your application and cryptoasset networks.

* *cryptoassets.core* framework is initialized from its own :doc:`configuration <./config>`, which can be passed in as Python dictionary or YAML configuration file.

Interacting with cryptoassets.core
-----------------------------------

The basic flow of using *cryptoassets.core* framework is

* You set up :py:class:`cryptoassets.core.app.CryptoassetsApp` instance and configure it inside your Python code

* You also set up a channel how :doc:`cryptoassets helper service <./service>` process callbacks you app. Usually this happens over :doc:`HTTP web hooks <./config>`.

* You obtain SQLAlchemy session through :py:class:`cryptoassets.core.app.CryptoassetsApp.conflict_resolver` to interact with your cryptoasset database containing your customer transaction details.

* You obtain an instance to :py:class:`cryptoassets.core.app.models.Wallet`. Wallet contains accounting information: which assets and which transactions belong to which users. Usually your application requires one default shared wallet.

* After having the wallet set up, call various model API methods like :py:meth:`cryptoassets.core.app.models.Wallet.send`.

* For receiving the payments you need to create at least one receiving address (see :py:meth:`cryptoassets.core.app.models.Wallet.create_receiving_address`). *Cryptoassets helper service* triggers :doc:`events <api/events>` which your application listens to and then performs application logic when a payment or a deposit is received.

Example command-line application
========================================

Below is a simple Bitcoin wallet terminal application.

It uses pre-created account on `block.io <https://en.bitcoin.it/wiki/Testnet>`_ Bitcoin API service. The coins stored on the block.io account are not use real Bitcoins, but `Testnet <https://en.bitcoin.it/wiki/Testnet>`_ Bitcoins which are worthless and thus very useful for testing.

Application code
-------------------

.. note ::

    The example is tested only for UNIX systems (Linux and OSX). The authors do not have availability of Microsoft development environments to ensure Microsoft Windows compatibility.

Here is an example walkthrough how to set up a command line application.

To run this example::

    # Activate the virtualenv where cryptoassets is installed
    source venv/bin/activate

    # Run the application
    python example.py

Save this as ``example.py`` file.

.. literalinclude:: example.py
    :language: python

Example configuration
----------------------

Save this as ``example.config.yaml`` file.

.. literalinclude:: example.config.yaml
    :language: yaml

Creating the database structure
---------------------------------

The example application uses `SQLite <http://www.sqlite.org/>`_ database. SQLite is a simple SQL database in a self contained file.

Install Python SQLite driver (be sure you do this in the activated virtual environment)::

    pip install sqlite3

Create the database tables::

    cryptoassets-initialize-database example.config.yaml

This should print out::

    [11:49:16] cryptoassets.core version 0.0
    [11:49:16] Creating database tables for sqlite:////tmp/cryptoassets.example.sqlite

Running the example
---------------------

:doc:`First make sure you have created a virtualenv, installed cryptoassets.core and its dependencies <./install>`.

Running the example application::

    python example.py

You should see something like this::

    Welcome to cryptoassets example app

    Receiving addresses available:
    (Send Testnet Bitcoins to them to see what happens)
    - 2MzGzEUyHgqBXzbuGCJDSBPKAyRxhj2q9hj: total received 0.00000000 BTC

    We know about the following transactions:

    Give a command
    1) Create new receiving address
    2) Send bitcoins to other address
    3) Quit

The application is fully functional and you can start your Bitcoin testnet wallet business right away. Only one more thing to do...

...the communication with cryptoasset network is handled by the :doc:`cryptoassets helper service <./service>` background process. Thus, nothing comes in or goes out to your application before you start the helper process::

    # Run this command in another terminal
    cryptoassets-helper-service example.config.yaml

You will get some *Rescanned transactions* log messages on the start up if you didn't change the default block.io credentials. These are test transactions from other example users.

Now you can send or receive Bitcoins within your application. If you don't start the helper service the application keeps functioning, but all external cryptoasset network traffic is being buffered until the *cryptoassets helper service* is running again.

If you want to reset the application just delete the database file ``/tmp/cryptoassets.test.sqlite``.

Obtaining testnet bitcoins and sending them
----------------------------------------------

The example runs on Bitcoin testnet bitcoins which are not real bitcoins.

Get Testnet coins from here:

* http://tpfaucet.appspot.com/

* `Alternative testnet faucets <http://bitcoin.stackexchange.com/questions/17690/is-there-any-where-to-get-free-testnet-bitcoins>`_

No more than **0.01** testnet bitcoins are needed for the example.

Send them to the receiving address displayed in the eaxmples application status. You should see a notification printed for incoming transaction in ~30 seconds after you send the bitcoins.

After completing the example
===============================

Explore :doc:`model API documentation <api/models>`, :doc:`configuration <config>` and :doc:`what tools there are available <api/functionality>`.

Django integration
--------------------

If you are using `Django <http://djangoproject.com/>`_ see `cryptoassets.django package <https://bitbucket.org/miohtama/cryptoassets.django>`_.

More about SQLAlchemy
-------------------------

Please see these tutorials

* (Official SQLAlchemy tutorial)

* http://www.pythoncentral.io/sqlalchemy-orm-examples/

Questions?
----------

:doc:`See the community resources <./community>`.