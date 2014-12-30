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

Initialize the database structure::

    cryptoassets-initializedb

Running the example
---------------------

:doc:`First make sure you have created a virtualenv, installed cryptoassets.core and its dependencies <./install>`.

Running the example application::

    python example.py

You can receive and send testnet coins, but the actual sending and receiving is handled by the :doc:`helper service <./service>`. Thus, nothing comes in or goes out before you start the helper process::

    # Run this command in another terminal
    cryptoassetshelper

Django integration
=======================

See ``cryptoassets.django package <https://bitbucket.org/miohtama/cryptoassets.django>``_.

More about SQLAlchemy
=======================

Please see these tutorils

* http://www.pythoncentral.io/sqlalchemy-orm-examples/ (filtering, etc.)