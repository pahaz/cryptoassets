================================
Configuration
================================

.. contents:: :local:

Introduction
--------------

*cryptoassets.core* must know about databases and backends you wish to use in your application.

You can give the configuration as

* Python dict

* YAML configuration file

Database
----------

Supported cryptoassets
-----------------------

Wallet notify
---------------

Wallet notify configuration tells how *cryptoassets helper service* should receive wallet updates from the cryptoassets backend (*bitcoind*, API service).

Named UNIX pipe
++++++++++++++++

HTTP webhook
++++++++++++++++

Event handling
---------------

Event handling configuration tells :doc:`cryptoassets helper service <./service>` how to notify your application about occured events (transaction updates, etc.). There exist various means to communicate between your application and *cryptoassets helper service*.

Event handling is configured in the ``events`` section of the configuration file.

Example::

HTTP webhook
+++++++++++++

Logging
--------

*cryptoassets.core* uses `standard Python logging <https://docs.python.org/3/library/logging.html>`_.

You can configure it with `Python logging configuration <https://docs.python.org/3/howto/logging.html#configuring-logging>`_.