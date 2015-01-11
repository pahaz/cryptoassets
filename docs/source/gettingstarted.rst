================================
Getting started
================================

.. contents:: :local:

Introduction
==============

*cryptoassets.core* provides safe, scalable and future-proof cryptocurrency and cryptoassets management for your Python application. It is built on the top of *SQLAlchemy* technology.

Basics
======

* You can use *cryptoassets.core* library in any Python application, including Django applications.

* *cryptoassets.core* support various cryptocurrencies and assets and is easily to extend support your favorite altcoint

* *cryptoassets.core* works with various API services (block.io, blockchain.info) and daemons (*bitcoind*, *dogecoind*). You either to sign up for an account on any the API services or run the daemon on your own server. Please note that running *bitcoind* requires at least 2 GB of RAM and 20 GB of disk space.

* :doc`For data integrity reasons <./integrity>`, *cryptoassets.core* uses its own database or database connection.

* Some basic `SQLAlchemy <http://www.sqlalchemy.org/>`_ knowledge might be required.

* *cryptoassets.core* runs a separate :doc:`helper service process <./service>` which multiplexes communication between your application and different crypto networks

* *cryptoassets.core* is initialized from its own :doc:`configuration <./config>`, which can be passed in as Python dictionary or YAML configuration file.

Interacting with cryptoassets.core
-----------------------------------

The basic interaction happens as following

* You set up :py:class:`cryptoassets.core.app.CryptoassetsApp` instance and configure it

* You also set up a channel how :doc:`cryptoassets helper service <./service>` process can call you app, like over :doc:`HTTP web hooks <./config>`. Minimally this is needed to get events from incoming transactions.

* You obtain SQLAlchemy session through :py:class:`cryptoassets.core.app.CryptoassetsApp.conflict_resolver` to interact with database

* You obtain an instance to :py:class:`cryptoassets.core.app.models.Wallet` - most applications have only one shared wallet

* You call various wallet methods like :py:class:`cryptoassets.core.app.models.Wallet.send`

* Your application listens to incoming transaction update :doc:`events <api/events>` and performs application logic when a payment is received

Example command-line application
========================================

Below is a simple terminal application which allows you to store,

It uses pre-created account on `block.io <https://en.bitcoin.it/wiki/Testnet>`_ Bitcoin API service. The coins stored on the API service account are not use real Bitcoins, but `Testnet <https://en.bitcoin.it/wiki/Testnet>`_ Bitcoins which are worthless and thus very useful for testing.

Application code
-------------------

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

Install Python SQLite driver (in the virtual environment)::

    pip install sqlite3

Create the database tables::

    cryptoassets-initialize-database example.config.yaml

Running the example
---------------------

:doc:`First make sure you have created a virtualenv, installed cryptoassets.core and its dependencies <./install>`.

Running the example application::

    python example.py

You can receive and send testnet coins, but the actual sending and receiving is handled by the :doc:`helper service <./service>`. Thus, nothing comes in or goes out to your application before you start the helper process::

    # Run this command in another terminal
    cryptoassets-helper-service

Now you can send or receive Bitcoins within your application.

After completing the example
===============================

Explore :doc:`model API documentation <api/models>`, :doc:`configuration <config>` and :doc:`what tools there are available <api/functionality>`.

Django integration
=======================

If you are using `Django <http://djangoproject.com/>`_ see `cryptoassets.django package <https://bitbucket.org/miohtama/cryptoassets.django>`_.

More about SQLAlchemy
=======================

Please see these tutorils

* http://www.pythoncentral.io/sqlalchemy-orm-examples/ (filtering, etc.)