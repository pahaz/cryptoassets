================================
Security and data integrity
================================

.. contents:: :local:

Introduction
-------------

When dealing with financial transactions, `especially ones which cannot be reversed <>`_, it is imperative that one gets its transaction handling correctly. *cryptoassets.core* provides tools and methods, so that even inexperienced developers do not shoot themselves into a foot when writing cryptoassets code.

Potential issues and threads for cryptoassets services include

* Race conditions allowing over-balance withdrawals or account balance mix up (data integrity issues)

* Partially lost data on unclean service shutdown

* Partially lost data when having Internet connectivity issues

* Database damage with bad migration

* Improper cold wallet handling increases the risk of losing customer assets

Below is how cryptoassets.core deals with these issues

Transaction integrity
----------------------

The production *cryptoassets.core* always runs its database transactions on `serializable transactino isolation level <http://en.wikipedia.org/wiki/Isolation_%28database_systems%29#Serializable>`_. This is not the default level of most database setups. Serializable transactions isolation level means that each transaction would happen in a complete isolation, one after each another, and thus there cannot be race conditions. If the database detects a race condition, only one of conflicting transactions may pass through and the others are aborted with application-level exception.

Data integrity on unclean shutdown
-----------------------------------

xxx

Migrations
------------

MySQL InnoDB engine is known not to be migration safe. *cryptoassets.core* recommends avoiding MySQL databases for financial applications.