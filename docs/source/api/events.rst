================================
Events
================================

.. contents:: :local:

Introduction
==============

*cryptoassets.core* fires events which your application may listen. Most interesting once are:

* New incoming transaction

* New confirmations for incoming transactions

* New confirmations for outgoing transactions

**cryptoassets.core** offers a framework how you can flexbile queue notifications for your application, regardless of API service or cryptocurrency you work on.

E.g. your application may receive notifications over

* UNIX scripts

* Redis queues

Events
=======

.. note ::

    In the future the scope of the events will be expanded: cold wallet top ups, network issues, etc.

.. automodule:: cryptoassets.core.notify.events
 :members:

Event hooks
=============

Event hooks tell how *cryptoassets.core* will post the event to your application.

HTTP webhook
========================

.. automodule:: cryptoassets.core.notify.http
 :members:

In-process Python
========================

.. automodule:: cryptoassets.core.notify.python
 :members:

Incoming transaction confirmation updates
===========================================

Handling incoming transactions is as not as straightforward as one would hope, especially with limited APIs provided with *bitcoind* and its derivates. Incoming transaction event chain for *bitcoind* goes as following:

For 0 confirmations and 1 confirmations

# Receive raw cryptocurrency protocol packet
    * Read transaction from the network
# API service notification / bitcoind `walletnotify <http://stackoverflow.com/q/20517442/315168>`_ shell hook
    * Push out notification about the updated transaction status
# Cryptoassets helper service (``cryptoassets-helper``)
    * Catch the low level transaction update notification (via named pipe, HTTP hook)
    * Write updated transaction information to the database
    * Update account balances, etc.
    * Call all generic cryptoasets notification handlers
# Your application
    * Listen cryptoassets notifications
    * Process updated transaction

For 2 and more confirmations

# Cryptoassets helper service (``cryptoassets-helper``)
    * Run periodical open transaction update task - :pymod:`cryptoassets.core.tools.opentransactions`
    * Poll the *bitcond* for transactions where the confirmation count in the database has not reached the maximum threshold yet. This is 15 confirmations by default.
    * If the transaction confirmation count has changed in the backend.
        * Update account balances, etc.
        * Call all generic cryptoasets notification handlers

For 15 and more confirmations

* These transactions are not polled anymore in the backend and are considered final.

* The threshold can be adjusted in :doc:`backend settings <../config>`.
