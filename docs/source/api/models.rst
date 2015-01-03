===================
Base models
===================

.. contents:: :local:

Base models describe how ``cryptoassets.core`` handles any cryptocurrency on the database level.
`SQLAlchemy library <http://www.sqlalchemy.org/>`_ is used for modeling.

Models are abstract and when you instiate a new cryptocurrency,
you inherit from the base classes and set the cryptocurrency specific properties.
For details, see :doc:`coin documentation <../coins>`.

Example from `cryptoassets.core.coin.bitcoin``::


    class BitcoinAccount(models.GenericAccount):
        coin = "btc"
        _wallet_cls_name = "BitcoinWallet"
        _address_cls_name = "BitcoinAddress"


    class BitcoinAddress(models.GenericAddress):
        coin = "btc"
        _account_cls_name = "BitcoinAccount"


    class BitcoinTransaction(models.GenericConfirmationTransaction):
        coin = "btc"
        _wallet_cls_name = "BitcoinWallet"
        _account_cls_name = "BitcoinAccount"
        _address_cls_name = "BitcoinAddress"


    class BitcoinWallet(models.GenericWallet):
        coin = "btc"
        Address = BitcoinAddress
        Account = BitcoinAccount
        Transaction = BitcoinTransaction

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

Transactions
++++++++++++++

.. autoclass:: cryptoassets.core.models.GenericTransaction
 :members:

.. autoclass:: cryptoassets.core.models.GenericConfirmationTransaction
 :members:

Wallet
++++++++++++

.. autoclass:: cryptoassets.core.models.GenericWallet
 :members:
