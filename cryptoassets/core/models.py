"""Base classes for SQL Alchemy models.

A set of abstract base classes which each cryptocurrency can inherit from.
Some special dependencies and hints need to be given for subclasses in order for
SQLAlchemy to be able to generate tables correctly.

See cryptoassets.coin modules for examples.
"""

import datetime
from collections import Counter
from decimal import Decimal

from sqlalchemy import Column
from sqlalchemy import Integer
from sqlalchemy import Numeric
from sqlalchemy import String
from sqlalchemy import Date
from sqlalchemy import DateTime
from sqlalchemy import ForeignKey
from sqlalchemy import Enum
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy.orm import relationship
from sqlalchemy.orm import scoped_session
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm.session import Session
from sqlalchemy.schema import UniqueConstraint
from zope.sqlalchemy import ZopeTransactionExtension

# Create a thread-local DB session constructor
DBSession = scoped_session(sessionmaker(extension=ZopeTransactionExtension()))

Base = declarative_base()


def _now():
    return datetime.datetime.utcnow()


class NotEnoughAccountBalance(Exception):
    """The user tried to send too much from a specific account. """


class NotEnoughWalletBalance(Exception):
    """The user tried to send too much from a specific account.

    This should be only raised through coin backend API reply
    and we never check this internally.
    """


class SameAccount(Exception):
    """Cannot do internal transaction within the same account.

    """


class TableName:
    """Mix-in class to create database tables based on the coin name. """
    @declared_attr
    def __tablename__(cls):
        if not hasattr(cls, "coin"):
            # Abstract base class
            return None
        return cls.__name__.lower()


class CoinBackend:
    """Mix-in class to allow coin backend property on models."""

    #: Set by cryptoassets.app.CryptoassetsApp.setup_session
    backend = None


class GenericAccount(TableName, Base, CoinBackend):
    """ An account within the wallet.

    We associate addresses and transactions to one account.

    The accountn can be owned by some user (user's wallet), or it can be escrow account or some other form of automatic transaction account.

    The transaction between the accounts of the same wallet are internal
    and happen off-blockhain.

    A special account is reserved for network fees caused by outgoing transactions.
    """
    #: Special label for an account where wallet
    #: will put all network fees charged by the backend
    NETWORK_FEE_ACCOUNT = "Network fees"

    __abstract__ = True

    #: Running counter used in foreign key references
    id = Column(Integer, primary_key=True)

    #: Human-readable name for this account
    name = Column(String(255), )

    #: When this account was created
    created_at = Column(DateTime, default=_now)

    #: Then the balance was updated, or new address generated
    updated_at = Column(DateTime, onupdate=_now)

    #: Available internal balance on this account
    #: NOTE: Accuracy checked for bitcoin only
    balance = Column(Numeric(21, 8), default=0)

    def __init__(self):
        self.balance = 0

    @declared_attr
    def __tablename__(cls):
        return "{}_account".format(cls.coin)

    @declared_attr
    def wallet_id(cls):
        return Column(Integer, ForeignKey('{}_wallet.id'.format(cls.coin)))

    @declared_attr
    def wallet(cls):
        return relationship(cls._wallet_cls_name, backref="accounts")


class GenericAddress(TableName, Base):
    """ The base class for cryptocurrency addresses.

    We can know about receiving addresses which are addresses without our system where somebody can deposit cryptocurrency. We also know about outgoing addresses where somebody has sent cryptocurrency from our system. For outgoing addresses ``wallet`` reference is null.

    """
    __abstract__ = True

    #: Running counter used in foreign key references
    id = Column(Integer, primary_key=True)

    #: The string presenting the address label in the network
    address = Column(String(127), nullable=False)

    #: Human-readable label for this address. User for the transaction history listing of the user. Must be unique across the whole system.
    label = Column(String(255), unique=True)

    #: Received balance of this address
    #: NOTE: Numeric Accuracy checked for Bitcoin only ATM
    balance = Column(Numeric(21, 8), default=0, nullable=False)
    created_at = Column(DateTime, default=_now)
    updated_at = Column(DateTime, onupdate=_now)

    #: Archived addresses are no longer in active incoming transaction polling
    #: and may not appear in the user wallet list
    archived_at = Column(DateTime, default=None, nullable=True)

    @declared_attr
    def __tablename__(cls):
        return "{}_address".format(cls.coin)

    @declared_attr
    def account_id(cls):
        return Column(Integer, ForeignKey('{}_account.id'.format(cls.coin)))

    #: If account is set to nul then this is an external address
    @declared_attr
    def account(cls):
        """ The associated account for this class.

        NULL if this is an external address.
        """
        return relationship(cls._account_cls_name, backref="addresses")

    @declared_attr
    def __table_args__(cls):
        return (UniqueConstraint('account_id', 'address', name='_account_address_uc'),)


class GenericTransaction(TableName, Base):
    """ A transaction between accounts, incoming transaction or outgoing transaction.
    """
    __abstract__ = True

    #: Running counter used in foreign key references
    id = Column(Integer, primary_key=True)

    #: When this transaction become visible in our database
    created_at = Column(DateTime, default=_now)

    #: When the incoming transaction was credited on the account.
    #: For internal transactions it is instantly.
    #: For external transactions this is when the confirmation threshold is exceeded.
    credited_at = Column(DateTime, nullable=True, default=None)

    #: When this transaction was processed by the application.
    #: For outgoing transactions this is the broadcasting time.
    #: For incoming transactions, your application may call
    #: ``mark_as_processed`` to mark it has handled the transaction.
    processed_at = Column(DateTime, nullable=True, default=None)

    #: Amount in the cryptocurrency minimum unit
    #: Note: Accuracy checked for Bitcoin only
    amount = Column(Numeric(21, 8))

    #: Different states this transaction can be
    #:
    #: **pending**: outgoing transaction waiting for the broadcast
    #:
    #: **broadcasted**: outgoing transaction has been sent to the network
    #:
    #: **incoming**: we see the transaction incoming to our system, but the confirmation threshold is not exceeded yet
    #
    #: **processed**: the application marked this transaction as handled and cryptoassets.core stops trying to notify your application about the transaction
    #:
    #: **internal**: This transaction was between the accounts within one of our wallets
    #:
    #: **network_fee**: When the transaction has been broadcasted, we create an internal transaction to account the occured network fees
    #:
    state = Column(Enum('pending', 'broadcasted', 'incoming', 'processed', 'internal', 'network_fee', 'balance_import', name="transaction_state"))

    #: Human readable label what this transaction is all about.
    #: Must be unique for each account
    label = Column(String(255), nullable=True)

    #: Eternal transaction id associated with this transaction.
    #: E.g. Bitcion transaction hash.
    txid = Column(String(255), nullable=True)

    # Dynamically generated attributes based on the coin name

    @declared_attr
    def __tablename__(cls):
        return "{}_transaction".format(cls.coin)

    @declared_attr
    def address_id(cls):
        return Column(Integer, ForeignKey('{}_address.id'.format(cls.coin)), nullable=True)

    @declared_attr
    def wallet_id(cls):
        return Column(Integer, ForeignKey('{}_wallet.id'.format(cls.coin)), nullable=False)

    @declared_attr
    def sending_account_id(cls):
        return Column(Integer, ForeignKey('{}_account.id'.format(cls.coin)))

    @declared_attr
    def receiving_account_id(cls):
        return Column(Integer, ForeignKey('{}_account.id'.format(cls.coin)))

    @declared_attr
    def address(cls):
        """ External cryptocurrency network address associated with the transaction.

        For outgoing transactions this is the walletless Address object holding only
        the address string.

        For incoming transactions this is the Address object with the reference
        to the Account object who we credited for this transfer.
        """
        return relationship(cls._address_cls_name,  # noqa
            primaryjoin="{}.address_id == {}.id".format(cls.__name__, cls._address_cls_name),
            backref="addresses")

    @declared_attr
    def sending_account(cls):
        """ The account where the payment was made from.
        """
        return relationship(cls._account_cls_name,  # noqa
            primaryjoin="{}.sending_account_id == {}.id".format(cls.__name__, cls._account_cls_name),
            backref="sent_transactions")

    @declared_attr
    def receiving_account(cls):
        """ The account which received the payment.
        """
        return relationship(cls._account_cls_name,  # noqa
            primaryjoin="{}.receiving_account_id == {}.id".format(cls.__name__, cls._account_cls_name),
            backref="received_transactions")

    @declared_attr
    def wallet(cls):
        """ Which Wallet object contains this transaction.
        """
        return relationship(cls._wallet_cls_name, backref="transactions")

    def can_be_confirmed(self):
        """ Return if the transaction can be considered as final.
        """
        return True

    def __str__(self):
        return "TX id:{} state:{} txid:{} sending acco:{} receiving acco:{}".format(self.id, self.state, self.txid, self.sending_account and self.sending_account.id, self.receiving_account and self.receiving_account.id)


class GenericConfirmationTransaction(GenericTransaction):
    """ Mined transaction which receives "confirmations" from miners in blockchain.
    """
    __abstract__ = True

    #: How many miner confirmations this tx has received
    confirmations = Column(Integer)

    #: How many confirmations to wait until the transaction is set as confirmed.
    #: TODO: Make this configurable.
    confirmation_count = 3

    def can_be_confirmed(self):
        """ Does this transaction have enough confirmations it could be confirmed by our standards. """
        return self.confirmations >= self.confirmation_count


class GenericWallet(TableName, Base, CoinBackend):
    """ A generic wallet implemetation.

    Inside the wallet there is a number of accounts.

    We support internal transaction between the accounts of the same wallet as off-chain transactions. If you call ``send()``for the address which is managed by the same wallet, an internal transaction is created by ``send_internal()``.

    When you send cryptocurrency out from the wallet, the transaction is put to the outgoing queue. Only after you call ``wallet.broadcast()`` the transaction is send out. This is to guarantee the system responsiveness and fault-tolerance, so that outgoing transactions can be created even if we have lost the connection with the cryptocurrency network. Calling ``broadcast()`` should the responsiblity of an external cron-job like process.
    """

    __abstract__ = True

    #: Running counter used in foreign key references
    id = Column(Integer, primary_key=True)

    #: The human-readable name for this wallet. Only used for debugging purposes.
    name = Column(String(255), unique=True)

    #: When this wallet was created
    created_at = Column(Date, default=_now)

    #: Last time when the balance was updated or new receiving address created.
    updated_at = Column(Date, onupdate=_now)

    #: The total balance of this wallet in the minimum unit of cryptocurrency
    #: NOTE: accuracy checked for Bitcoin only
    balance = Column(Numeric(21, 8))

    #: Reference to the Address class used by this wallet
    Address = None

    #: Reference to the Transaction class used by this wallet
    Transaction = None

    #: Reference to the Account class used by this wallet
    Account = None

    @declared_attr
    def __tablename__(cls):
        return "{}_wallet".format(cls.coin)

    def __init__(self):
        self.balance = 0

    @classmethod
    def get_by_id(cls, session, wallet_id):
        """Returns an existing wallet instance by its id.

        :return: Wallet instance
        """

        assert wallet_id
        assert type(wallet_id) == int

        instance = session.query(cls).get(wallet_id)
        return instance

    @classmethod
    def get_or_create_by_name(cls, name, session):
        """Returns a new or existing instance of a named wallet.

        :return: Wallet instance
        """

        assert name
        assert type(name) == str

        instance = session.query(cls).filter_by(name=name).first()

        if not instance:
            instance = cls()
            instance.name = name
            session.add(instance)

        return instance

    def create_account(self, name):
        """Create a new account inside this wallet.

        :return: GenericAccout object
        """

        session = Session.object_session(self)

        assert session

        account = self.Account()
        account.name = name
        account.wallet = self
        session.add(account)
        return account

    def get_account_by_name(self, name):
        session = Session.object_session(self)
        instance = session.query(self.Account).filter_by(name=name).first()
        return instance

    def get_or_create_account_by_name(self, name):
        session = Session.object_session(self)
        instance = session.query(self.Account).filter_by(name=name).first()
        if not instance:
            instance = self.create_account(name)

        return instance

    def get_or_create_network_fee_account(self):
        """Lazily create the special account where we account all network fees.

        This is for internal bookkeeping only. These fees MAY be
        charged from the users doing the actual transaction, but it
        must be solved on the application level.
        """
        return self.get_or_create_account_by_name(self.Account.NETWORK_FEE_ACCOUNT)

    def create_receiving_address(self, account, label):
        """ Creates a new receiving address.

        All incoming transactions on this address
        are put on the given account.

        :param account: GenericAccount object

        :param label: Label for this address - must be human-readable, generated and unique. E.g. "Joe's wallet #2"

        :return: GenericAddress object
        """

        session = Session.object_session(self)

        assert session
        assert account
        assert label
        assert account.id

        _address = self.backend.create_address(label=label)

        address = self.Address()
        address.address = _address
        address.account = account
        address.label = label
        address.wallet = self

        session.add(address)

        # Make sure the address is written to db before we can make any entires of received transaction on it in monitoring
        session.flush()

        # XXX: Need to get rid of this
        self.backend.monitor_address(address)

        return address

    def get_or_create_external_address(self, address):
        """ Create an accounting entry for an address which is outside our system.

        When we send out external transactions, they go to these address entries.
        These addresses do not have wallet or account connected to our system.

        :param address: Address as a string
        """

        assert type(address) == str

        session = Session.object_session(self)

        _address = session.query(self.Address).filter_by(address=address, account_id=None).first()
        if not _address:
            _address = self.Address()
            _address.address = address
            _address.account = None
            _address.label = "External {}".format(address)
            session.add(_address)

        return _address

    def send(self, from_account, receiving_address, amount, label, force_external=False):
        """ Send the amount of cryptocurrency to the target address.

        If the address is hosted in the same wallet do the internal accounting,
        otherwise go through the publib blockchain.

        :param account: The account owner from whose balance we

        :return: Transaction object
        """
        session = Session.object_session(self)

        assert isinstance(from_account, self.Account)
        assert type(receiving_address) == str
        assert isinstance(amount, Decimal)

        internal_receiving_address = session.query(self.Address).filter(self.Address.address == receiving_address).first()
        if internal_receiving_address and not force_external:
            to_account = internal_receiving_address.account
            return self.send_internal(from_account, to_account, amount, label)
        else:
            return self.send_external(from_account, receiving_address, amount, label)

    def add_address(self, account, label, address):
        """ Adds an external address under this wallet, under this account.

        This is for the cases where the address already exists in the existing backend wallet,
        but our database does not know about its existince.

        :param account: Account instance

        :param address: Address instance
        """
        session = Session.object_session(self)

        assert session, "Tried to add address to a non-bound wallet object"

        address_obj = self.Address()
        address_obj.address = address
        address_obj.account = account
        address_obj.label = label
        session.add(address_obj)
        # Make sure the address is written to db
        # before we can make any entires of received
        # transaction on it in monitoring
        session.flush()
        self.backend.monitor_address(address_obj)
        return address_obj

    def get_accounts(self):
        session = Session.object_session(self)
        # Go through all accounts and all their addresses

        return session.query(self.Account).filter(self.Account.wallet_id == self.id)  # noqa

    def get_account_by_address(self, address):
        """Check if a particular address belongs to receiving address of this wallet and return its account.

        This does not consider bitcoin change addresses and such.

        :return: Account instance or None if the wallet doesn't know about the address
        """
        session = Session.object_session(self)
        addresses = session.query(self.Address).filter(self.Address.address == address).join(self.Account).filter(self.Account.wallet_id == self.id)  # noqa
        _address = addresses.first()
        if _address:
            return _address.account
        return None

    def get_receiving_addresses(self, archived=False):
        """ Get all receiving addresses for this wallet.

        This is mostly used by the backend to get the list
        of receiving addresses to monitor for incoming transactions
        on the startup.

        :param expired: Include expired addresses
        """

        session = Session.object_session(self)

        if archived:
            raise RuntimeError("TODO")

        # Go through all accounts and all their addresses
        return session.query(self.Address).filter(self.Address.archived_at == None).join(self.Account).filter(self.Account.wallet_id == self.id)  # noqa

    def get_external_received_transactions(self):
        """Get all external transactions to this wallet.

        Returns both unconfirmed and confirmed transactions.

        :return: SQLAlchemy query
        """

        session = Session.object_session(self)

        # Go through all accounts and all their addresses
        # XXX: Make state handling more robust
        return session.query(self.Transaction).filter(self.Transaction.sending_account == None, self.Transaction.address != None, self.Transaction.txid != None)  # noqa

    def get_active_external_received_transcations(self):
        """Return all incoming transactions which are still pending.

        :return: SQLAlchemy query
        """
        return self.get_external_received_transactions().filter(self.Transaction.credited_at == None).join(self.Address)  # noqa

    def refresh_account_balance(self, account):
        """Refresh the balance for one account.

        If you have imported any addresses, this will recalculate balances from the backend.

        TODO: This method will be replaced with wallet import.

        TODO: This screws ups bookkeeping, so DON'T call this on production.
        It doesn't write fixing entries yet.

        :param account: GenericAccount instance
        """
        session = Session.object_session(self)

        assert session
        assert account.wallet == self

        addresses = session.query(self.Address).filter(self.Address.account == account).values("address")

        total_balance = 0

        # The backend might do exists checks using in operator
        # to this, we cannot pass generator, thus list()
        for address, balance in self.backend.get_balances(list(item.address for item in addresses)):
            total_balance += balance
            session.query(self.Address).filter(self.Address.address == address).update({"balance": balance})

        account.balance = total_balance

    def send_internal(self, from_account, to_account, amount, label, allow_negative_balance=False):
        """ Tranfer currency internally between the accounts of this wallet.

        :param from_account: GenericAccount

        :param to_account: GenericAccount

        :param amount: The amount to transfer in wallet book keeping unit
        """
        session = Session.object_session(self)

        assert from_account.wallet == self
        assert to_account.wallet == self
        # Cannot do internal transactions within the account
        assert from_account.id
        assert to_account.id
        assert session

        if from_account.id == to_account.id:
            raise SameAccount("Trying to do internal transfer on account id {}".format(from_account.id))

        if not allow_negative_balance:
            if from_account.balance < amount:
                raise NotEnoughAccountBalance()

        transaction = self.Transaction()
        transaction.sending_account = from_account
        transaction.receiving_account = to_account
        transaction.amount = amount
        transaction.wallet = self
        transaction.credited_at = _now()
        transaction.label = label
        session.add(transaction)

        from_account.balance -= amount
        to_account.balance += amount

        return transaction

    def send_external(self, from_account, to_address, amount, label):
        """ Create a new external transaction and put it to the transaction queue.

        The transaction is not send until `broadcast()` is called
        for this wallet.

        :param to_address: Address as a string

        :return: Transaction object
        """
        session = Session.object_session(self)

        assert session
        assert from_account.wallet == self

        # TODO: Currently we don't allow
        # negative withdrawals on external sends
        #
        if from_account.balance < amount:
            raise NotEnoughAccountBalance()

        _address = self.get_or_create_external_address(to_address)

        transaction = self.Transaction()
        transaction.sending_account = from_account
        transaction.amount = amount
        transaction.state = "pending"
        transaction.wallet = self
        transaction.address = _address
        transaction.label = label
        session.add(transaction)

        from_account.balance -= amount
        self.balance -= amount

        return transaction

    def broadcast(self):
        """ Broadcast all pending external send transactions.

        This is desgined to be run from a background task,
        as this might be blocking operation or the backend connection might be down.

        :return: The number of succesfully broadcasted transactions
        """

        session = Session.object_session(self)

        # Get all outgoing pending transactions
        txs = session.query(self.Transaction).filter(self.Transaction.state == "pending", self.Transaction.receiving_account == None)  # noqa

        # XXX: Rewrite

        outgoing = Counter()
        for tx in txs:
            assert tx.address
            assert tx.amount > 0
            assert isinstance(tx.address, self.Address)
            outgoing[tx.address.address] += tx.amount

        if outgoing:
            txid, fee = self.backend.send(outgoing, "Cryptoassets tx {}".format(tx.id))
            assert txid
            txs.update(dict(state="broadcasted", processed_at=_now(), txid=txid))

            if fee:
                self.charge_network_fees(txs, txid, fee)

        return len(outgoing)

    def charge_network_fees(self, txs, txid, fee):
        """ Account network fees due to transaction broadcast.

        By default this creates a new accounting entry on a special account
        (`GenericAccount.NETWORK_FEE_ACCOUNT`) where the network fees are put.

        :param txs: Internal transactions participating in send

        :param txid: External transaction id

        :param fee: Fee as the integer
        """

        session = Session.object_session(self)

        fee_account = self.get_or_create_network_fee_account()

        # TODO: Not sure which one is better approach
        # assert fee_account.id, "Fee account is not properly constructed, flush() DB"
        session.flush()

        transaction = self.Transaction()
        transaction.sending_account = fee_account
        transaction.receiving_account = None
        transaction.amount = fee
        transaction.state = "network_fee"
        transaction.wallet = self
        transaction.label = "Network fees for {}".format(txid)
        transaction.txid = txid

        fee_account.balance -= fee
        self.balance -= fee

        session.add(fee_account)
        session.add(transaction)

    def refresh_total_balance(self):
        """ Make the balance to match with the actual backend.

        This is only useful for send_external() balance checks.
        Actual address balances will be out of sync after calling this
        (if the balance is incorrect).
        """
        self.balance = self.backend.get_balance()

    def receive(self, txid, address, amount, extra=None):
        """Informs the wallet updates regarding external incoming transction.

        This method should be called by the coin backend only.

        Write the transaction to the database.
        Notify the application of the new transaction status.
        Wait for the application to mark the transaction as processed.

        Note that we may receive the transaction many times with different confirmation counts.

        :param txid: External transaction id

        :param address: Address as a string

        :param amount: Int, as the basic currency unit

        :param extra: Extra variables to set on the transaction object as a dictionary. E.g. `dict(confirmations=5)`.

        :return: tuple (account, new or existing Transaction object)
        """

        session = Session.object_session(self)

        assert self.id
        assert amount > 0, "Receiving transaction to {} with amount {}".format(address, amount)
        assert txid
        assert type(address) == str

        _address = session.query(self.Address).filter(self.Address.address == address).first()  # noqa

        assert _address, "Wallet {} does not have address {}".format(self.id, address)
        assert _address.id

        # TODO: Have something smarter here after we use relationships
        account = session.query(self.Account).filter(self.Account.id == _address.account_id).first()  # noqa
        assert account.wallet == self

        # Check if we already have this transaction
        transaction = session.query(self.Transaction).filter(self.Transaction.txid == txid, self.Transaction.address_id == _address.id).first()
        if not transaction:
            # We have not seen this transaction before in the database
            transaction = self.Transaction()
            transaction.txid = txid
            transaction.address = _address
            transaction.state = "incoming"
            transaction.wallet = self
            transaction.amount = amount

        transaction.sending_account = None
        transaction.receiving_account = account
        session.add(transaction)

        #
        # TODO: Move confirmation code to a separate subclass
        #

        # Copy extra transaction payload
        if extra:
            for key, value in extra.items():
                setattr(transaction, key, value)

        if not transaction.credited_at:

            if transaction.can_be_confirmed():
                # Consider this transaction to be confirmed and update the receiving account
                transaction.credited_at = _now()
                account.balance += transaction.amount
                _address.balance += transaction.amount
                account.wallet.balance += transaction.amount

                session.add(account)

        return account, transaction

    def mark_transaction_processed(self, transaction_id):
        """ Mark that the transaction was processed by the client application.

        This will stop retrying to post the transaction to the application.
        """

        session = Session.object_session(self)

        assert type(transaction_id) == int

        # Only non-archived addresses can receive transactions
        transactions = session.query(self.Transaction.id, self.Transaction.state).filter(self.Transaction.id == transaction_id, self.Transaction.state == "incoming")  # noqa

        # We should mark one and only one transaction processed
        assert transactions.count() == 1

        transactions.update(dict(state="processed", processed_at=_now()))
