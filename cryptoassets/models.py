"""Base classes for SQL Alchemy models.

A set of abstract base classes which each cryptocurrency can inherit from.
Some special dependencies and hints need to be given for SQL Alchemy in order for it
to be able to generate tables correctly.



"""

import datetime
from collections import Counter

from sqlalchemy import Column
from sqlalchemy import Integer
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

from .backend import registry as backendregistry

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

    @property
    def backend(self):
        """Return the configured coin backend for this model.

        Pulls the associated backend instance (block.io, blockchain.info, etc)
        for the registry.
        """
        return backendregistry.get(self.coin)


class GenericAccount(TableName, Base, CoinBackend):

    #: Special label for an account where wallet
    #: will put all network fees charged by the backend
    NETWORK_FEE_ACCOUNT = "Network fees"

    __abstract__ = True
    id = Column(Integer, primary_key=True)
    name = Column(String(255), )
    created_at = Column(DateTime, default=_now)
    updated_at = Column(DateTime, onupdate=_now)
    balance = Column(Integer, default=0)

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

    def lock(self):
        """ Get a lock context manager to protect operations targeting this account.

        This lock must be acquired for all operations touching the balance.
        """
        return self.backend.get_lock("{}_account_lock_{}".format(self.coin, self.id))


class GenericAddress(TableName, Base):
    """Baseclass for cryptocurrency addresses.


    """
    __abstract__ = True
    id = Column(Integer, primary_key=True)
    address = Column(String(127), nullable=False)
    label = Column(String(255), unique=True)
    balance = Column(Integer, default=0, nullable=False)
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
    id = Column(Integer, primary_key=True)
    created_at = Column(DateTime, default=_now)
    credited_at = Column(DateTime, nullable=True, default=None)
    processed_at = Column(DateTime, nullable=True, default=None)
    amount = Column(Integer())
    state = Column(Enum('pending', 'broadcasted', 'incoming', 'processed', 'internal', 'network_fee'))

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


class GenericConfirmationTransaction(GenericTransaction):
    """ Mined transaction which receives "confirmations" from miners in blockchain.
    """
    __abstract__ = True

    #: How many miner confirmations this tx has received
    confirmations = Column(Integer)

    confirmation_count = 3

    def can_be_confirmed(self):
        """ Does this transaction have enough confirmations it could be confirmed by our standards. """
        return self.confirmations >= self.confirmation_count


class GenericWallet(TableName, Base, CoinBackend):
    """ A wallet implementation supporting shared / internal transactions. """

    __abstract__ = True
    id = Column(Integer, primary_key=True)
    name = Column(String(255))
    created_at = Column(Date, default=_now)
    updated_at = Column(Date, onupdate=_now)
    balance = Column(Integer())

    # Subclass must set these
    # class references to corresponding models
    Address = None
    Transaction = None
    Account = None

    @declared_attr
    def __tablename__(cls):
        return "{}_wallet".format(cls.coin)

    def __init__(self):
        self.balance = 0

    def lock(self):
        """ Get a lock context manager to protect operations targeting this account.

        This lock must be acquired for all operations touching the wallet balance,
        or adding a new address.
        """
        return self.backend.get_lock("{}_wallet_lock_{}".format(self.coin, self.id))

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

    def get_or_create_network_fee_account(self):
        """Lazily create the special account where we account all network fees.

        This is for internal bookkeeping only. These fees MAY be
        charged from the users doing the actual transaction, but it
        must be solved on the application level.
        """
        session = Session.object_session(self)
        instance = session.query(self.Account).filter_by(name=self.Account.NETWORK_FEE_ACCOUNT).first()
        if not instance:
            instance = self.create_account(self.Account.NETWORK_FEE_ACCOUNT)

        return instance

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

        with self.lock():

            _address = self.backend.create_address(label=label)

            address = self.Address()
            address.address = _address
            address.account = account
            address.label = label
            address.wallet = self

            session.add(address)

            # Make sure the address is written to db
            # before we can make any entires of received
            # transaction on it in monitoring
            session.flush()

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

        internal_receiving_address = session.query(self.Address).filter(self.Address.address == receiving_address).first()
        if internal_receiving_address and not force_external:
            to_account = session.query(self.Account).get(internal_receiving_address.account)
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
        return session.query(self.Transaction).filter(self.Transaction.sending_account == None, self.Transaction.txid != None)  # noqa

    def get_active_external_received_transcations(self):
        """Return all incoming transactions which are still pending.

        :return: SQLAlchemy query
        """
        return self.get_external_received_transactions().filter(self.Transaction.credited_at == None).join(self.Address)  # noqa

    def refresh_account_balance(self, account):
        """ Refresh the balance for one account.

        If you have imported any addresses, this will recalculate balances from the backend.

        TODO: This screws ups book keeping, so DON'T call this on production.
        It doesn't write fixing entries yet.

        :param account: GenericAccount instance
        """
        session = Session.object_session(self)

        assert account.wallet == self

        with account.lock():
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

        with from_account.lock(), to_account.lock():

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

        with from_account.lock(), self.lock():

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

        broadcast_lock = self.backend.get_lock("{}_broadcast_lock".format(self.coin, self.id))
        with broadcast_lock:
            outgoing = Counter()
            for tx in txs:
                assert tx.address
                assert tx.amount > 0
                assert isinstance(tx.address, self.Address)
                outgoing[tx.address.address] += tx.amount

            if outgoing:
                txid, fee = self.backend.send(outgoing)
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

        with fee_account.lock():
            fee_account.balance -= fee

        with self.lock():
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

        :return: new or existing Transaction object
        """

        session = Session.object_session(self)

        assert self.id
        assert amount > 0
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

                with self.lock():
                    self.balance += transaction.amount

                session.add(account)

        return transaction

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
