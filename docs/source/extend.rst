================================
Extending
================================

.. contents:: :local:

Introduction
-------------

*cryptoassets.core* has extensible architecture

* You can easily include new crytocurrencies and assets

* You can choose to use any protocol backend instead of *bitcoind*

* You can override almost any part of the system with your own class or subclass

.. note ::

    Currently the architecture is heavily geared towards mined coins. This will change in the future and class hiearchy is abstracted so that traits like mining (block confirmations) go into their own class tree. Alternatively, consensus based coins (Ripple, Stellar) get their own corresponding base classes.

Adding new cryptocurrency model
---------------------------------

Adding support for *bitcoind* derived altcoin is as easy as creating models file (for example see :py:mod:`cryptoassets.core.coin.applebyte.mdoels`) and givin the models module in :doc:`the config file <./config>`. You can use the stock :py:mod:`cryptoassets.core.backend.bitcoind` if altcoin is JSON-RPC compatible with *bitcoind* (they are).

Adding support for non-bitcoin like cryptoassets includes subclassing API classes and having corresponding backend.  You can still use services like :doc:`database transaction conflict resolution <./integrity>`.

Adding new cryptocurrecy backend
----------------------------------------------------------------------

Subclass :py:class:`cryptoassets.core.backend.base.CoinBackend`.

Create a backend specific unit test which subclasses :py:class:`cryptoassets.core.tests.base.CoinTestCase`. If all `CoinTestCase` tests passed, your backend is more or less feature complete and complete with *cryptoassets.core*.

Overriding parts of the framework
------------------------------------

You can switch and replace any part of the framework. For example, you might want to optimize certain components, like *bitcoind* connections for scalability.

* Database models can be overridden with :doc:`models configuration <./config>` and thus you can replace any stock API method with your own.

* You can :doc:`plug in your own backend <./extend>`.

* You can subclass :py:class:`cryptoassets.core.app.CryptoassetsApp` and override initialization methods to plug-in your own code.