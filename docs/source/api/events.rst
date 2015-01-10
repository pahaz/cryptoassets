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

*cryptoassets.core* will also post more complex events in the future (cold wallet top ups, etc.).

Events
=============

*cryptoassets.core* currently sends the following events.

.. note ::

    In the future the scope of the events will be expanded: cold wallet top ups, network issues, etc.

.. automodule:: cryptoassets.core.notify.events
 :members:

Event handlers
===============

Event handlers tell how *cryptoassets.core* will post the event to your application.

**cryptoassets.core** offers a framework how you can flexbile queue notifications for your application, regardless of API service or cryptocurrency you work on.

* If you want to your web server process handle events, configure HTTP webhook

* If you want to run event handling code inside *cryptoasset helper service*, use in-process Python notifications

HTTP webhook
----------------

.. automodule:: cryptoassets.core.notify.http
 :members:

In-process Python
--------------------

.. automodule:: cryptoassets.core.notify.python
 :members:

Shell script
--------------------

.. automodule:: cryptoassets.core.notify.script
 :members:

Incoming transaction confirmation updates
===========================================

Handling incoming cryptoasset transactions is as not as straightforward as one would hope, especially with limited APIs provided with *bitcoind* and its derivates. Incoming transaction event chain for *bitcoind* goes as following:

For 0 confirmations and 1 confirmations

# Receive raw cryptocurrency protocol packet
    * Read transaction from the network
# API service notification / bitcoind :doc:`walletnotify <../backends>` shell hook
    * Push out notification about the updated transaction status
# Cryptoassets helper service (``cryptoassets-helper``)
    * Catch the low level transaction update notification (via named pipe, HTTP hook)
    * Write updated transaction information to the database
    * Update account balances, etc.
    * Call all generic cryptoasets notification handlers with ``txupdate`` event
# Your application
    * Listen for ``txupdate`` event
    * Process updated transaction

For 2 and more confirmations

# Cryptoassets helper service (``cryptoassets-helper``)
    * Run periodical open transaction update task - :py:mod:`cryptoassets.core.tools.opentransactions`
    * Poll the *bitcond* for transactions where the confirmation count in the database has not reached the maximum threshold yet. This is 15 confirmations by default.
    * If the transaction confirmation count has changed in the backend.
        * Update account balances, etc.
        * Call all generic cryptoasets notification handlers

For 15 and more confirmations

* These transactions are not polled anymore in the backend and are considered final.

* The threshold can be adjusted in :doc:`backend settings <../config>`.
