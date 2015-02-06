================================
Utilities
================================

.. contents:: :local:

Introduction
--------------

Here is collection of helper classes.

Transaction conflict resolver
------------------------------

.. automodule:: cryptoassets.core.utils.conflictresolver
 :members:

Conflict resolver unit tests provide tests for different transaction conflict resolution outcomes and their resolution. If you are unsure Python database driver can handle transaction conflicts, this is a good smoke test to find out.

.. automodule:: cryptoassets.core.tests.test_conflictresolver
 :members: PostgreSQLConflictResolverTestCase

Automatic enumeration classes
------------------------------

.. automodule:: cryptoassets.core.utils.enum
 :members:

Python dictionary deep merge
------------------------------

.. automodule:: cryptoassets.core.utils.dictutil
 :members:

HTTP event listener decorator
------------------------------

.. automodule:: cryptoassets.core.utils.httpeventlistener
    :members: simple_http_event_listener
