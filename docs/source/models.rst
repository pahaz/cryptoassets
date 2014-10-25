===================
Models
===================

Models describe the database tables in Python.

Models are abstract and when you instiate a new cryptocurrency,
you inherit from the base classes and set the cryptocurrency specific properties.

Example from `cryptoassets.coin.bitcoin::


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

Using wallet
---------------

The normal usage pattern is following:

Create one shared wallet for the website. Usually the websites have shared wallets, unless you are building the wallet service itself.

Create an account for the user inside the shared wallet.

Create new receiving address for the account of the use.

Let the user transfer in some cryptocurrency.

Now the cryptocurrency from the user wallet can be used to pay or fund actions on your website.

Because the cryptocurrency is credited on the account, we can do instant internal transactions and bookkeeping for the actions.

The user is free to withdraw the cryptocurrency away.

