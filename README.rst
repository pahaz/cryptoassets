cryptoassets.core
==================

.. image:: https://drone.io/bitbucket.org/miohtama/cryptoassets/status.png
    :target: https://drone.io/bitbucket.org/miohtama/cryptoassets/latest

.. image:: https://readthedocs.org/projects/cryptoassetscore/badge/?version=latest
    :target: http://cryptoassetscore.readthedocs.org/en/latest/

.. contents:: :local:

A Python library for building Bitcoin and cryptocurrency service. Provide Bitcoin, cryptocurrency and cryptoassets APIs, database models and accounting.

Benefits
----------------------------------------------------------------------

* Easy: Documented user-friendly APIs

* Extensible: Any cryptocurrency and cryptoassets support

* Safe: Secure and high data integrity

* Lock-in free: Vendor independent and platform agnostics

* Customizable: Override any part of the framework

Requirements and installation
--------------------------------

* Python 3

You need to install database support libraries separately, depending on which database you are using.

See `Installation <http://cryptoassetscore.readthedocs.org/en/latest/>_.

Getting started
---------------

See `Getting started tutorial <http://cryptoassetscore.readthedocs.org/en/latest/gettingstarted.html>`_.

Documentation
---------------

`The documentation is on readthedocs.org <http://cryptoassetscore.readthedocs.org/en/latest/>`_.

Supported environments
------------------------

Cryptocurrencies and assets
++++++++++++++++++++++++++++++

* Bitcoin

* Dogecoin

* Litecoin

* AppleByte

It is easy to add support for any cryptocurrency.

Databases
++++++++++++++++++++

* PostgreSQL

* SQLite

* MySQL

* Oracle

`For the full list see SQLAlchemy dialects documentation <http://docs.sqlalchemy.org/en/rel_0_9/dialects/index.html>`_.

Daemons and wallet services
++++++++++++++++++++++++++++++++++++++

*cryptoassets.core* can operate with a cryptocurrency daemon or third party API service.

Example daemons and services include:

* *bitcoind* and bitcoind-compatible altcoins (Dogecoin, Litecoin, etc.)

* `block.io <https://block.io>`_ (Bitcoin, Dogecoin, Litecoin)

* `blockchain.info <http://blockchain.info>`_ (Bitcoin)

Python frameworks
+++++++++++++++++++++++++++

You can integrate *cryptoassets.core* on

* Pyramid

* Django (see `cryptoassets.django package for Django integration <https://bitbucket.org/miohtama/cryptoassets.django>`_)

* Flask

... and any other Python application where `SQLAlchemy can be run <http://www.sqlalchemy.org/>`_.


Source
--------

The source can be browsed at `Bitbucket <https://bitbucket.org/miohtama/cryptoassets/src>`_.

License
----------

`MIT <http://opensource.org/licenses/MIT>`_

Author
---------

Mikko Ohtamaa (`blog <https://opensourcehacker.com>`_, `Facebook <https://www.facebook.com/?q=#/pages/Open-Source-Hacker/181710458567630>`_, `Twitter <https://twitter.com/moo9000>`_, `Google+ <https://plus.google.com/u/0/103323677227728078543/>`_)


