================================
Security and data integrity
================================

.. contents:: :local:

Introduction
-------------

When dealing with financial transactions, `especially ones which cannot be reversed <http://blog.stakeventures.com/articles/2012/03/07/the-may-scale-of-money-hardness-and-bitcoin>`_, it is imperative that one gets its transaction handling correctly. *cryptoassets.core* provides tools and methods, so that even inexperienced developers do not shoot themselves into a foot when writing cryptoassets code.

This includes mitigation against

* Human-errors by the developers

* External attackers trying to exploit issues in the financial code

Potential issues and threads for cryptoassets services include

* Race conditions allowing over-balance withdrawals or account balance mix up (data integrity issues)

* Double transaction broadcasts doing double withdrawals from hot wallet

* Partially lost data on unclean service shutdown

* Partially lost data when having Internet connectivity issues

* Database damage with bad migration

* Improper cold wallet handling increases the risk of losing customer assets

Below is how cryptoassets.core addresses these issues.

Eliminating race conditions
-------------------------------

The production *cryptoassets.core* always runs its database transactions on `serializable transactino isolation level <http://en.wikipedia.org/wiki/Isolation_%28database_systems%29#Serializable>`_. Note that this is not the default for most database setups. Serializable transactions isolation level means that each transaction would happen in a complete isolation, one after each another, and thus there cannot be race conditions. If the database detects transactions touching the same data, only one of conflicting transactions may pass through and the others are aborted with application-level exception.

Serializable transaction isolation simply prevents all kind of race conditions. Alternative would be writing application level locking code, which is prone to errors, as it incumbers more cognitive overhead for the developers themselves. Better let the database developers take care of the locking, as they have liven their life by solving concurrency issues and they are expert on it.

However the developers most deal with conflicting transaction rollbacks. *cryptoassets.core* provides tools to handle this in idomatic Python way.

More information

* `PostgreSQL transaction isolation levels <http://www.postgresql.org/docs/devel/static/transaction-iso.html>`_

Data integrity on failed broadcasts
----------------------------------------------------------------------

One possible error condition is not knowing if the outgoing transaction was broadcasted. For example, you send out a transaction and the network connection to *bitcoind* dies, or server goes down, just about when *bitcoind* is about to write JSON-RPC API reply "transaction broadcasted".

When *cryptoassets.core* does outgoing transaction broadcasts, it separately commits when broadcast was started (``opened_at``) when broadcast was ended (``closed_at``). Broadcasts which never receives ending mark is considered "broken" and :doc:`cryptoassets helper service <./service>` never managed to write to the database whether this broadcast got out to the network or not.

For broken transactions one needs to manually check from blockchain, by matching ``opened_at`` timestamp and transaction amount, whether the broadcast made to blockchain before the broadcasting process failed.

* Set ``txid`` and ``closed_at`` for the transactions if they got out to blockchain

* Remove ``opened_at`` timestamp if the transaction never made to the blockchain and should be rebroadcasted

Missed incoming transactions
------------------------------

For a reason or another, *cryptoassets.core* may miss the initial :doc:`wallet notification <./backends>` from the network for new deposit transaction arriving to the address in your application wallet. Particularly, *cryptoassets helper service* could be down when the transaction was broadcasted.

*cryptoassets helper service* rescans all receiving addresses on start up. Thus, restarting *cryptoassets helper service* fixes the problem. Alternatively, you can manually run :doc:`rescan command <./service>`.

Missed transactions confirmations
----------------------------------

For a reason or another, your application may fail to process transaction update events.

E.g.

* Event hook calling your application failed

* *Cryptoassets helper service* was down when :doc:`wallet notification <./backends>` arrived

*Cryptoassets helper service* will poll all transactions where the transaction confirmation count is below a :doc:`threshold value <./config>`. If you miss confirmation notification *cryptoassets.core* will simple keep polling the transaction again and again until it manages to update the confirmation count.

Migrations
------------

`MySQL InnoDB engine is known not to be migration safe <http://blog.ionelmc.ro/2014/12/28/terrible-choices-mysql/>`_. *cryptoassets.core* recommends avoiding MySQL databases for financial applications.