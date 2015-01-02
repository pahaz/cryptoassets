================================
Configuration
================================

.. contents:: :local:

Introduction
================

*cryptoassets.core* must know about cryptocurrencies, databases and backends you use in your application.

Creating application object and configuring it
================================================

Most of interaction with *cryptoassets.core* is done through :py:class:`cryptoassets.core.app.CryptoAssetsApp` application object. Create one singleton instance within your application:

.. highlight:: python

    from cryptoassets.core.app import CryptoAssetsApp

    assets_app = CryptoAssetsApp()

Configuring using YAML configuration file
--------------------------------------------------------

Use :py:method:`cryptoassets.configuration.Configuraror.load_yaml_file` to load `YAML syntax <http://en.wikipedia.org/wiki/YAML>`_ config file:

.. highlight:: python

    from cryptoassets.core.app import CryptoAssetsApp
    from cryptoassets.core.configuration import Configurator

    assets_app = CryptoAssetsApp()

    # This will load the configuration file for the cryptoassets framework
    configurer = Configurator(assets_app)
    configurer.load_yaml_file("my-cryptoassets-settings.yaml")

Example YAML configuration file:

.. literalinclude:: example.config.yaml
    :language: yaml

Configuring using Python dict
------------------------------------------

You can give your settings as Python dictionary:

.. highlight:: python

    CRYPTOASSETS_SETTINGS = {

        # You can use a separate database for cryptoassets,
        # or share the Django database. In any case, cryptoassets
        # will use a separate db connection.
        "database": {
            "url": "postgresql://localhost/cryptoassets",
            "echo": True,
        },

        # What cryptocurrencies we are configuring to the database
        "models": {
            "btc": "cryptoassets.core.coin.bitcoin.models"
        },

        # Locally running bitcoind in testnet
        "backends": {
            "btc": {
                "class": "cryptoassets.core.backend.bitcoind.Bitcoind",
                "url": "http://foo:bar@127.0.0.1:8332/",
                # Cryptoassets helper process will use this UNIX named pipe to communicate
                # with bitcoind
                "walletnotify": {
                    "class": "cryptoassets.core.backend.httpwalletnotify.HTTPWalletNotifyHandler",
                    "ip": "127.0.0.1"
                    "port": 28882
                },
            }
        },
    }

    configurator.load_from_dict(CRYPTOASSETS_SETTINGS)

Configuration sections
========================

database
----------

Configure usd SQLAlchemy database connection.

Example::

        "database": {
            "url": "postgresql://localhost/cryptoassets",
            "echo": true,
        }

.. note::

    The database connection will always use Serializable transaction isolation level.

For more information see

* :doc:`Data integrity <./integrity>`

* `SQLAlchemy isolation_level <http://docs.sqlalchemy.org/en/latest/core/connections.html#sqlalchemy.engine.Connection.execution_options.params.isolation_level>`_

url
++++++++

`SQLAlchemy connection URL <http://docs.sqlalchemy.org/en/latest/core/engines.html>`_.

echo
+++++

Set to ``true`` (or Python `True``) and all SQL statements will be logged via Python logging.

coins
-----------------------

Configure database models and used backends for cryptocurrencies and assets enabled in your application.

This dictonary contains a list of subentries.

* Name of each entry is acronym of the cryptoasset in lowercase (``btc``, ``doge``)

Example::


    "coins": {
        # AppleByte using applebyted (bitcoind-like) as the backend
        "aby": {
            "backend": {
                "class": "cryptoassets.core.backend.bitcoind.Bitcoind",
                "url": "http://x:y@127.0.0.1:8607/",
                "walletnotify": {
                    "class": "cryptoassets.core.backend.httpwalletnotify.HTTPWalletNotifyHandler",
                    "ip": "127.0.0.1",
                    "port": 28882
                },
            },
        },
    },

backend
++++++++++

Available backends.

walletnotify
++++++++++++++

Wallet notify configuration tells how :doc:`cryptoassets helper service <:/service> receives cryptoasset transaction updates from the cryptoassets backend (bitcoind, API service). Unless this is configured, cryptoassets service or your application won't know about incoming transactions.

Usually you must configure your backend to send notifications to cryptoassets helper service e.g. by editing ``bitcoin.conf`` and entering ``walletnotify`` configure setting.

Example configuration for receiving walletnotify notifications over a named UNIX pipe::

    backend:
        class: cryptoassets.core.backend.bitcoind.Bitcoind
        url: http://foo:bar@127.0.0.1:8332/
        walletnotify:
            class: cryptoassets.core.backend.pipewalletnotify.PipedWalletNotifyHandler
            fname: /tmp/cryptoassets-unittest-walletnotify


Named UNIX pipe
~~~~~~~~~~~~~~~~~

.. automodule:: cryptoassets.core.backend.pipewalletnotify

HTTP webhook
~~~~~~~~~~~~~~~~~

.. automodule:: cryptoassets.core.backend.httpwalletnotify

Redis pubsub
~~~~~~~~~~~~~~~~~

.. automodule:: cryptoassets.core.backend.rediswalletnotify

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