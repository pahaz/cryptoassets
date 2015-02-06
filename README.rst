cryptoassets.core
==================

.. |docs| image:: https://readthedocs.org/projects/cryptoassetscore/badge/?version=latest
    :target: http://cryptoassetscore.readthedocs.org/en/latest/

.. |ci| image:: https://drone.io/bitbucket.org/miohtama/cryptoassets/status.png
    :target: https://drone.io/bitbucket.org/miohtama/cryptoassets/latest

.. |cov| image:: https://codecov.io/bitbucket/miohtama/cryptoassets/coverage.svg?branch=master
    :target: https://codecov.io/bitbucket/miohtama/cryptoassets?branch=master

.. |downloads| image:: https://pypip.in/download/cryptoassets.core/badge.png
    :target: https://pypi.python.org/pypi/cryptoassets.core/
    :alt: Downloads

.. |latest| image:: https://pypip.in/version/cryptoassets.core/badge.png
    :target: https://pypi.python.org/pypi/cryptoassets.core/
    :alt: Latest Version

.. |license| image:: https://pypip.in/license/cryptoassets.core/badge.png
    :target: https://pypi.python.org/pypi/cryptoassets.core/
    :alt: License

.. |versions| image:: https://pypip.in/py_versions/cryptoassets.core/badge.png
    :target: https://pypi.python.org/pypi/cryptoassets.core/
    :alt: Supported Python versions

*cryptoassets.core* is a Python framework for building Bitcoin, other cryptocurrency (altcoin) and cryptoassets services. Use cases include eCommerce, exhanges, wallets and payments.

+-----------+-----------+
| |docs|    | |cov|     |
+-----------+-----------+
| |ci|      | |license| |
+-----------+-----------+
| |versions|| |latest|  |
+-----------+-----------+
||downloads||           |
+-----------+-----------+

.. contents:: :local:

Benefits
----------------------------------------------------------------------

* `Easy <http://cryptoassetscore.readthedocs.org/en/latest/gettingstarted.html>`_: Documented user-friendly APIs

* `Extensible <http://cryptoassetscore.readthedocs.org/en/latest/extend.html>`_: Any cryptocurrency and cryptoassets support

* `Safe <http://cryptoassetscore.readthedocs.org/en/latest/integrity.html>`_: Secure and high data integrity

* `Lock-in free <http://cryptoassetscore.readthedocs.org/en/latest/backends.html>`_: Vendor independent and platform agnostics

* `Customizable <http://cryptoassetscore.readthedocs.org/en/latest/extend.html#overriding-parts-of-the-framework>`_: Override and tailor any part of the framework for your specific needs

Requirements and installation
--------------------------------

* Python 3

You need to install database support libraries separately, depending on which database you are using.

See `Installation <http://cryptoassetscore.readthedocs.org/en/latest/>`_.

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

* `Bitcoin <http://cryptoassetscore.readthedocs.org/en/latest/coins.html#bitcoin>`_

* `Dogecoin <http://cryptoassetscore.readthedocs.org/en/latest/coins.html#dogecoin>`_

* `Litecoin <http://cryptoassetscore.readthedocs.org/en/latest/coins.html#litecoin>`_

* `Applebyte <http://cryptoassetscore.readthedocs.org/en/latest/coins.html#applebyte>`_

It is easy to `add support for any cryptocurrency <http://cryptoassetscore.readthedocs.org/en/latest/extend.html>`_.

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

* `bitcoind <http://cryptoassetscore.readthedocs.org/en/latest/backends.html#module-cryptoassets.core.backend.bitcoind>`_ and bitcoind-compatible altcoins (Dogecoin, Litecoin, etc.)

* `block.io <http://cryptoassetscore.readthedocs.org/en/latest/backends.html#module-cryptoassets.core.backend.blockio>`_ (Bitcoin, Dogecoin, Litecoin)

* `blockchain.info <http://cryptoassetscore.readthedocs.org/en/latest/backends.html#module-cryptoassets.core.backend.blockchain>`_ (Bitcoin)

Python frameworks
+++++++++++++++++++++++++++

You can integrate *cryptoassets.core* on

* Pyramid

* Django (see `Django integration <https://bitbucket.org/miohtama/cryptoassets.django>`_)

* Flask

... and any other Python application where `SQLAlchemy can be run <http://www.sqlalchemy.org/>`_.

Source code and issue tracking
--------------------------------

The project source code is hosted at `Bitbucket <https://bitbucket.org/miohtama/cryptoassets/src>`_.

License
----------

`MIT <http://opensource.org/licenses/MIT>`_

Author
---------

Mikko Ohtamaa (`blog <https://opensourcehacker.com>`_, `Facebook <https://www.facebook.com/?q=#/pages/Open-Source-Hacker/181710458567630>`_, `Twitter <https://twitter.com/moo9000>`_, `Google+ <https://plus.google.com/u/0/103323677227728078543/>`_)


