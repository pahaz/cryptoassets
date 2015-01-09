===================
Base models
===================

.. contents:: :local:

Base models describe how *cryptoassets.core* handles any cryptocurrency on the database level.
`SQLAlchemy library <http://www.sqlalchemy.org/>`_ is used for modeling.

Models are abstract and when you instiate a new cryptocurrency,
you inherit from the base classes and set the cryptocurrency specific properties.

Models also specify the core API how to interact with *cryptoassets.core*

*

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

.. autoclass:: cryptoassets.core.models.GenericNetworkTranacttion
 :members:

.. autoclass:: cryptoassets.core.models.GenericConfirmationNetworkTranacttion
 :members:

Wallet
++++++++++++

.. autoclass:: cryptoassets.core.models.GenericWallet
 :members:
