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

.. code-block:: python

    from cryptoassets.core.app import CryptoAssetsApp

    assets_app = CryptoAssetsApp()

Configuring using YAML configuration file
--------------------------------------------------------

Use :py:meth:`cryptoassets.configuration.Configuraror.load_yaml_file` to load `YAML syntax <http://en.wikipedia.org/wiki/YAML>`_ config file:

.. code-block:: python

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

.. code-block:: python

    CRYPTOASSETS_SETTINGS = {

        # You can use a separate database for cryptoassets,
        # or share the Django database. In any case, cryptoassets
        # will use a separate db connection.
        "database": {
            "url": "postgresql://localhost/cryptoassets",
            "echo": True,
        },

        # Locally running bitcoind in testnet
        "coins": {
            "btc": {
                "backend": {
                    "class": "cryptoassets.core.backend.bitcoind.Bitcoind",
                    "url": "http://x:y@127.0.0.1:9999/",

                    # bitcoind has 60 seconds to get back to us
                    "timeout": 60,

                    # Cryptoassets helper process will use this UNIX named pipe to communicate
                    # with bitcoind
                    "walletnotify": {
                        "class": "cryptoassets.core.backend.httpwalletnotify.HTTPWalletNotifyHandler",
                        "ip": "127.0.0.1",
                        "port": 28882
                   },
                },

                # We run in testnet mode
                "testnet": True
            },
        },
    }

    configurator.load_from_dict(CRYPTOASSETS_SETTINGS)

Configuration sections
========================

database
----------

Configure usd SQLAlchemy database connection.

.. code-block:: python

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

Set to ``true`` (or in Python to ``True``) and `executed SQL statements will be logged via Python logging <http://stackoverflow.com/a/2950685/315168>`_.

coins
-----------------------

Configure database models and used backends for cryptocurrencies and assets enabled in your application.

This dictonary contains a list of subentries.

* Name of each entry is acronym of the cryptoasset in lowercase (``btc``, ``doge``)

Example:

.. code-block:: python


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

        "bitcoin": {
            "backend": {
                "class": "cryptoassets.core.backend.bitcoind.Bitcoind",
                "url": "http://foo:bar@127.0.0.1:8332/"
                "max_tracked_incoming_confirmations": 20,
                "walletnotify":
                    "class": "cryptoassets.core.backend.pipewalletnotify.PipedWalletNotifyHandler",
                    "fname": "/tmp/cryptoassets-unittest-walletnotify"
            }
        }
    },

models
++++++++

**Optional**.

You can set up your own altcoin or override :doc:`default SQLAlchemy model configuration <api/models>` for an existing cryptoasset.

The value of this variable is the Python module containing ``coin_description`` variable. For more information how to describe your cryptoasset models, see :py:mod:`cryptoassets.core.coin.registry`.

Example:

.. code-block:: python

        "jesuscoin": {
            "backend": {
                "class": "cryptoassets.core.backend.bitcoind.Bitcoind",
                "url": "http://x:y@127.0.0.1:8607/",
                "walletnotify": {
                    "class": "cryptoassets.core.backend.httpwalletnotify.HTTPWalletNotifyHandler",
                    "ip": "127.0.0.1",
                    "port": 28882
                },
            },
            "models": "mycoin.models"
        },


max_confirmation_count
+++++++++++++++++++++++++++

This is how many confirmations ``tools.confirmationupdate`` tracks for each network transactions, both incoming and outgoing, until we consider it "closed" and stop polling backend for updates. The default value is ``15``.

For more information see :py:mod:`cryptoassets.core.tools.confirmationupdate`.

backend
++++++++++

Installed backends for one cryptoasset in ``coins`` section.

For the available backends see :doc:`backends list <./backends>`.

Each backend contains the following options

:param class: tells which backend we are going to use

:param walletnofiy: tells what kind of incoming transaction notifications we have from the backend

:param max_tracked_incoming_confirmations: This applications for mined coins and backends which do not actively post confirmations updates. It tells up to how many confirmations we poll the backend for confirmation updates. For details see :py:mod:`cryptoassets.core.tools.opentransactions`.

**Other options**: All backends take connection details (url, IPs) and credentials (passwords, API keys, etc.) These options are backend specific, so see the details from the :doc:`backend documentation <./backends>.

walletnotify
++++++++++++++++

:doc:`Wallet notify <./backends>` configuration tells how :doc:`cryptoassets helper service <./service>` receives cryptoasset transaction updates from the cryptoassets backend (bitcoind, API service). Unless this is configured, cryptoassets service or your application won't know about incoming transactions.

``walletnotify`` section must be given in under backend configuration. It's content depends on the chosen wallet notifiaction method. For more information see :doc:`qallet notification documentation <./backends>`.

events
---------------

Event handling is configured in the ``events`` section of the configuration file.

Event handling configuration tells how :doc:`cryptoassets helper service <./service>` notifies your application about occured events (transaction updates, etc.). There exist various means to communicate between your application and *cryptoassets helper service*.

For more information and examples read :doc:`event API documentation <api/events>`.

Event section consists name and configuration data pairs. Currently event handler name is only used for logging purposes. You can configure multiple event handlers

Each handler gets **class** parameters and event handler specific setup parameters.

Example configuration

.. code-block:: python

    # List of cryptoassets notification handlers.
    # Use this special handler to convert cryptoassets notifications to Django signals.
    "events": {
        "django": {
            "class": "cryptoassets.core.event.python.InProcessNotifier",
            "callback": "cryptoassets.django.incoming.handle_tx_update"
        }
    },

status_server
---------------

Configure mini status server which you can use to check *cryptoassets helper service* status.

ip
++++++++++

IP address the status server will be listening to. Default 127.0.0.1.

port
++++++++++

Port the status server is listening to.s


Logging
--------

*cryptoassets.core* uses `standard Python logging <https://docs.python.org/3/library/logging.html>`_.

For logging within your application when calling :doc:`model methods <api/models>` configure logging with `Python logging configuration <https://docs.python.org/3/howto/logging.html#configuring-logging>`_.

For configuring logging for *cryptoassets helper service* please wait for upcoming updates.

