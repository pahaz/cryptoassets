================================
Getting started
================================

.. contents:: :local:

Introduction
==============

``cryptoassets.core`` provides safe, scalable and future-proof cryptocurrency and cryptoassets management for your Python application. It is built on the top of *SQLAlchemy* technology.

Basics
======

* You can use ``cryptoassets.core`` library in any Python application, including Django applications.

* ``cryptoassets.core`` support various cryptocurrencies and assets and is designed to be extended to support
everything

* ``cryptoassets.core`` works with various cryptocurrency API services (block.io, blockchain.info) or with protocl daemons (``bitcoind``, ``dogecoind``). You need to choose either to register account on any of API services or run the daemon on your own server. Please note that running ``bitcoind`` requires at least 2 GB of RAM and 20 GB of disk space.

* Some basic SQLAlchemy knowledge might be required. It is mostly covered in this documentation.

* ``cryptoassets.core`` uses its own database or database connections to store cryptoasset transaction and accounting information. For the safety reasons used database connections has very high transaction isolation level, which your normal web application might not do.

* ``cryptoassetes.core`` requires running a separate :doc:`helper service process <./service>` which takes are of communicating with various Python network.

* ``cryptoassets.core`` is initialized from its own configuration which can be passed in as Python dictionary or YAML configuration file.

Walkthrough
============

Here is an example walkthrough how to set up a command line application.

To run this example::

    # Activate the virtualenv where cryptoassets is installed
    source venv/bin/activate

    # Run the application
    python example.py

Example code::

.. literalinclude:: example.py
    :language: python


Example application
-------------------

Running the example application::

xx

Example configuration
----------------------

xxx

Creating database
------------------

xx

Running the application
------------------------

xxx

Running the helper service
----------------------------

xxx

More about SQLAlchemy
----------------------

Please see these tutorils

* http://www.pythoncentral.io/sqlalchemy-orm-examples/ (filtering, etc.)