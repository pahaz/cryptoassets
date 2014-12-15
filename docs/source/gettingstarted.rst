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

For Django users there is a separate, Django specific package and README you should follow.

Requirements
-------------

You need at least Python version 3.4.

* Install Python 3.4 on Ubuntu

* Install Python 3.4 on OSX

Older Python versions might be supported in the future if there is demand for the support.

Create a virtualenv
---------------------

``cryptoassets.core`` is distributed as a Python package. By following the Python community best create a virtualenv where you are going to install ``cryptoassets.core`` package and its dependencies.

Ubuntu. Ubuntu and Debian has an open issue regarding Python 3.4 virtualenv support. Thus, follow the instructions here carefully or refer to future best practices from Ubuntu community::

OSX::

    mkdir myproject
    cd myproject
    python3.4 -m venv venv
    source venv/bin/activate

Installing cryptoassets package
---------------------------------

After virtualenv is created and active you can run::

    pip install cryptoassets.core

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