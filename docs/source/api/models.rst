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

Model API conventions
----------------------

The following conventions are followed in the model API

Model discovery
~~~~~~~~~~~~~~~~~~~~

* Abstract base classes are called *GenericXxx* like *GenericWallet*.

* Actual class implementation is in ``coin`` module, e.g. :py:class:`cryptoassets.core.coin.bitcoin.models.BitcoinWallet`.

* You do not access the model classes directly, but through configured assets registry. E.g. to get a hold of ``BitcoinWallet`` class you do ``Wallet = cryptoassets_app.coins.get("btc").coin_model``.

* The usual starting point for the calls is to get or create :py:class:`cryptoassets.core.models.GenericWallet` instance. Check out :py:meth:`cryptoassets.core.models.GenericWallet.get_or_create_by_name`.

Session lifecycle
~~~~~~~~~~~~~~~~~~~~

* API tries to use the SQLAlchemy database session of the object if possible: ``Session.object_session(self)``. If not, session must be explicitly given and you get your session inside a helper closure function decorated by  :py:meth:`cryptoassets.core.utils.conflictresolver.ConflictResolver.managed_transaction`. This way we guarantee graceful handling of transaction conflicts.

* API never does ``session.flush()`` or ``session.commit()``

* API will do ``session.add()`` for newly created objects

Model classes
---------------

Below are the base classes for models. All cryptoassets have the same API as described these models.

Account
~~~~~~~~~~~~~~~~~~~~

.. autoclass:: cryptoassets.core.models.GenericAccount
 :members:

Address
~~~~~~~~~~~~~~~~~~~~

.. autoclass:: cryptoassets.core.models.GenericAddress
 :members:

Transaction
~~~~~~~~~~~~~~~~~~~~

.. autoclass:: cryptoassets.core.models.GenericTransaction
 :members:

NetworkTransaction
~~~~~~~~~~~~~~~~~~~~

.. autoclass:: cryptoassets.core.models.GenericNetworkTransaction
 :members:

.. autoclass:: cryptoassets.core.models.GenericConfirmationNetworkTransaction
 :members:

Wallet
~~~~~~~~~~~~~~~~~~~~

.. autoclass:: cryptoassets.core.models.GenericWallet
 :members:

Validation
----------------

.. automodule:: cryptoassets.core.coin.validate
 :members:
