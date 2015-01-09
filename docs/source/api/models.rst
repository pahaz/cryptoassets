===================
Base models
===================

.. contents:: :local:

Base models describe how *cryptoassets.core* handles any cryptocurrency on the database level.
`SQLAlchemy library <http://www.sqlalchemy.org/>`_ is used for modeling.

Models are abstract and when you instiate a new cryptocurrency,
you inherit from the base classes and set the cryptocurrency specific properties.

Models also specify the core API how to interact with *cryptoassets.core*

See :doc:`how to get started interacting with models <../gettingstarted>`.

For more information, see :doc:`coin documentation <../coins>` and how to :doc:`extend the framework with your own altcoins <../extend>`.

Cryptoasset registry
----------------------

.. automodule:: cryptoassets.core.coin.registry
 :members:

Default models
----------------

.. automodule:: cryptoassets.core.coin.defaults
 :members:


Model classes
---------------

Below are the base classes for models.

Account
++++++++++++

.. autoclass:: cryptoassets.core.models.GenericAccount
 :members:

Address
++++++++++++

.. autoclass:: cryptoassets.core.models.GenericAddress
 :members:

Transaction
++++++++++++++

.. autoclass:: cryptoassets.core.models.GenericTransaction
 :members:

NetworkTransaction
+++++++++++++++++++

.. autoclass:: cryptoassets.core.models.GenericNetworkTransaction
 :members:

.. autoclass:: cryptoassets.core.models.GenericConfirmationNetworkTransaction
 :members:

Wallet
++++++++++++

.. autoclass:: cryptoassets.core.models.GenericWallet
 :members:
