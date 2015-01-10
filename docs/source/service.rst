================================
Service and commands
================================

.. contents:: :local:


Introduction
--------------

Cryptoassets helper service is a standalone process responsible for communication between cryptocurrency networks, cryptocurrency API providers and your application.

Primarily Cryptoassets helper service

* Broadcasts new outgoing transactions to the cryptocurrency network

* Gets transaction notifications from cryptocurrency daemons and APIs and then notifies your application about the transaction updates

Even if network connections go down, you lose connection to APIs or cryptocurrency networks, cryptoassets library continuous to work somewhat indepedently. The users can send and receive transactions, which are buffered until the network becomes available again. Some functions, which are synchronous by nature, like creating new addresses, might not be available.

Besides providing a daemon for communications additional helping commands are available

* Initialize database

* Rescan wallet for missed transations

cryptoassetshelper
------------------

This command is the service helper process. It must be running on the background for your cryptoassets application to function properly.

Running the service with Python project
+++++++++++++++++++++++++++++++++++++++++++

After installing *cryptoassets.core* to your virtualenv you should be able to run the cryptoassets helper service as following::

    cryptoassethelper <your YAML config file>

Running the service with Django
+++++++++++++++++++++++++++++++++++++++++++

If you are running a `Django <https://www.djangoproject.com/>`_ application, a special `Django management command is provided by cryptoassets.django library <https://bitbucket.org/miohtama/cryptoassets.django>`_.

System service integration
+++++++++++++++++++++++++++++++++++++++++++

To have automatic start/stop and other functionality for cryptoassets helper service, use something akin *systemd* or `supervisord <http://supervisord.org/>`_.

cryptoassets-initialize-database
---------------------------------

This command will create database tables for different cryptocurrencies as described in the configuration file. Usually you need to do this only once when setting up the database.

cryptoassets-scan-received
----------------------------

Rescan all receiving addresses for missed deposit transactions.

This is also performed automatically on startup of *cryptoassets helper service*.

For more information see :py:mod:`cryptoassets.core.tools.receivescan`.

.. note ::

    At the moment it is not recommended to run this command while cryptoassetshelper is running on background.



