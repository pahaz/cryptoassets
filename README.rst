cryptoassets.core
==================

.. image:: https://drone.io/bitbucket.org/miohtama/cryptoassets/status.png
    :target: https://drone.io/bitbucket.org/miohtama/cryptoassets/latest

.. image:: https://readthedocs.org/projects/cryptoassetscore/badge/?version=latest
    :target: http://cryptoassetscore.readthedocs.org/en/latest/

.. contents:: :local:

A Python library for building Bitcoin and cryptocurrency service. Provide Bitcoin, cryptocurrency and cryptoassets APIs, database models and accounting.

Why to build your application of the top of cryptoassets.core
----------------------------------------------------------------------

* Easy, user-friendly, APIs.

* Accounting off the box: makes sure your business can generate bookeeping reports out of records.

* Safe - a lot of effort and experience goes into defensive programming and making this fault tolerant against human and network errors.

* Vendor independent: choose an API service or self-host a cryptocurrency daemon like bitcoind

* Use any cryptocurrency and support future currencies and assets through extensible framework.

* Customizable: you can override any part of the framework with a custom component if you need to scale up or specialize in the future.

Requirements
---------------

* Python 3

You need to install database support libraries separately, depending on which database you are using.

Getting started
---------------

See `Getting started tutorial <http://cryptoassetscore.readthedocs.org/en/latest/gettingstarted.html>`_.

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

Protocols, daemons and API services
++++++++++++++++++++++++++++++++++++++

``cryptoassets.core`` can operate with a cryptocurrency daemon or third party API service.

Example daemons and service include:

* *bitcoind* and bitcoind-compatible altcoins (Dogecoin, Litecoin, etc.)

* `block.io <https://block.io>`_ (Bitcoin, Dogecoin, Litecoin)

* `blockchain.info <http://blockchain.info>`_ (Bitcoin)

Python frameworks
++++++++++++++++++++

You can integrate ``cryptoassets.core`` on

* Pyramid

* Django (see `cryptoassets.django package for Django integration <https://bitbucket.org/miohtama/cryptoassets.django>`_)

* Flask

... and any other Python application where `SQLAlchemy can be run <http://www.sqlalchemy.org/>`_.

Documentation
---------------

`The documentation is on readthedocs.org <http://cryptoassetscore.readthedocs.org/en/latest/>`_.

Author
---------

Mikko Ohtamaa (`blog <https://opensourcehacker.com>`_, `Facebook <https://www.facebook.com/?q=#/pages/Open-Source-Hacker/181710458567630>`_, `Twitter <https://twitter.com/moo9000>`_, `Google+ <https://plus.google.com/u/0/103323677227728078543/>`_)


