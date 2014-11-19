================================
Notifications
================================

.. contents:: :local:

Introduction
==============

You wan to receive various notifications about cryptoassets transaction status

* New incoming transaction

* New confirmations for incoming transactions

* New confirmations for outgoing transactions

**cryptoassets.core** offers a framework how you can flexbile queue notifications for your application, regardless of API service or cryptocurrency you work on.

E.g. your application may receive notifications over

* UNIX scripts

* Redis queues

Event chain
=============

The events are processed as following::

# Receive raw cryptocurrency protocol packet
    * Read transaction from the network
# API service notification / bitcoind `walletnotify <http://stackoverflow.com/q/20517442/315168>`_ shell hook
    * Push out notification about the updated transaction status
# Cryptoassets helper service (``cryptoassets-helper``)
    * Catch the low level transaction update notification
    * Write updated transaction information to the database
    * Update account balances, etc.
    * Call all generic cryptoasets notification handlers
# Your application
    * Listen cryptoassets notifications
    * Process updated transaction
