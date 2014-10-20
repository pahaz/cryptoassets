import datetime
from collections import Counter

from sqlalchemy import (
    Column,
    Index,
    Integer,
    Text,
    String,
    Numeric,
    Date,
    ForeignKey,
    Enum,
    )

from sqlalchemy.orm.session import Session
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.ext.declarative import declared_attr

from sqlalchemy.orm import (
    scoped_session,
    sessionmaker,
    )

from zope.sqlalchemy import ZopeTransactionExtension

from .backend import registry as backendregistry

DBSession = scoped_session(sessionmaker(extension=ZopeTransactionExtension()))
Base = declarative_base()


def _now():
    return datetime.datetime.utcnow()


class NotEnoughAccountBalance(Exception):
    """ The user tried to send too much from a specific account. """


class NotEnoughWalletBalance(Exception):
    """ The user tried to send too much from a specific account.

    This should be only raised through coin backend API reply
    and we never check this internally.
    """


class TableName:

    @declared_attr
    def __tablename__(cls):
        if not hasattr(cls, "coin"):
            # Abstract base class
            return None
        return cls.__name__.lower()


class CoinBackend:

    @property
    def backend(self):
        return backendregistry.get(self.coin)


class GenericAccount(TableName, Base, CoinBackend):
    __abstract__ = True
    id = Column(Integer, primary_key=True)
    name = Column(String(255))
    created_at = Column(Date, default=_now)
    updated_at = Column(Date, onupdate=_now)
    balance = Column(Integer, default=0)

    def __init__(self):
        self.balance = 0

    @declared_attr
    def __tablename__(cls):
        return "{}_account".format(cls.coin)

    @declared_attr
    def wallet(cls):
        return Column(Integer, ForeignKey('{}_wallet.id'.format(cls.coin)))

    def lock(self):
        """ Get a lock context manager to protect operations targeting this account.

        This lock must be acquired for all operations touching the balance.
        """
        return self.backend.get_lock("{}_account_lock_{}".format(self.coin, self.id))


class GenericAddress(TableName, Base):
    __abstract__ = True
    id = Column(Integer, primary_key=True)
    address = Column(String(128), nullable=False, unique=True)
    label = Column(String(255), unique=True)
    balance = Column(Integer, default=0, nullable=False)
    created_at = Column(Date, default=_now)
    archived_at = Column(Date, onupdate=_now)

    @declared_attr
    def __tablename__(cls):
        return "{}_address".format(cls.coin)

    @declared_attr
    def account(cls):
        return Column(Integer, ForeignKey('{}_account.id'.format(cls.coin)))


class GenericTransaction(TableName, Base):
    """
    """
    __abstract__ = True
    id = Column(Integer, primary_key=True)
    created_at = Column(Date, default=_now)
    broadcasted_at = Column(Date, nullable=True, default=None)
    amount = Column(Integer())
    state = Column(Enum('pending', 'unconfirmed', 'broadcasted', 'invalid', 'internal'))
    txid = Column(String(255), nullable=True)

    @declared_attr
    def __tablename__(cls):
        return "{}_transaction".format(cls.coin)

    @declared_attr
    def address(cls):
        return Column(Integer, ForeignKey('{}_address.id'.format(cls.coin)))

    @declared_attr
    def wallet(cls):
        return Column(Integer, ForeignKey('{}_wallet.id'.format(cls.coin)), nullable=False)

    @declared_attr
    def sending_account(cls):
        return Column(Integer, ForeignKey('{}_account.id'.format(cls.coin)))

    @declared_attr
    def receiving_account(cls):
        return Column(Integer, ForeignKey('{}_account.id'.format(cls.coin)))


class GenericConfirmationTransaction(GenericTransaction):
    __abstract__ = True
    confirmations = Column(Integer)


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

        This lock must be acquired for all operations touching the balance.
        """
        return self.backend.get_lock("{}_wallet_lock_{}".format(self.coin, self.id))

    def create_account(self, name):
        """
        """

        session = Session.object_session(self)

        assert session

        account = self.Account()
        account.name = name
        account.wallet = self.id
        session.add(account)
        return account

    def create_receiving_address(self, account, label):
        """ Creates private/public key pair for receiving.
        """

        session = Session.object_session(self)

        assert session
        assert account
        assert label

        _address = self.backend.create_address(label=label)

        address = self.Address()
        address.address = _address
        address.account = account.id
        address.label = label

        session.add(address)

        return address

    def send(self, account, receiving_address, amount):
        """
        :param account: The account owner from whose balance we
        """

    def add_address(self, account, label, address):
        """ Adds an external address under this wallet, under this account. """
        session = Session.object_session(self)
        address_obj = self.Address()
        address_obj.address = address
        address_obj.account = account.id
        address_obj.label = label
        session.add(address_obj)
        return address_obj

    def refresh_account_balance(self, account):
        """ Refresh the balance for one account. """
        session = Session.object_session(self)

        assert account.wallet == self.id

        with account.lock():
            addresses = session.query(self.Address).filter(self.Address.account == account.id).values("address")

            total_balance = 0

            # The backend might do exists checks using in operator
            # to this, we cannot pass generator, thus list()
            for address, balance in self.backend.get_balances(list(item.address for item in addresses)):
                total_balance += balance
                session.query(self.Address).filter(self.Address.address == address).update({"balance": balance})

            account.balance = total_balance

    def send_internal(self, from_account, to_account, amount, label, allow_negative_balance=False):
        """
        """
        session = Session.object_session(self)

        assert from_account.wallet == self.id
        assert to_account.wallet == self.id
        # Cannot do internal transactions within the account
        assert from_account.id
        assert to_account.id
        assert from_account.id != to_account.id, "Trying to do internal transfer on account id {}".format(from_account.id)
        assert session

        with from_account.lock(), to_account.lock():

            if not allow_negative_balance:
                if from_account.balance < amount:
                    raise NotEnoughAccountBalance()

            transaction = self.Transaction()
            transaction.sending_account = from_account.id
            transaction.receiving_account = to_account.id
            transaction.amount = amount
            transaction.wallet = self.id
            session.add(transaction)

            from_account.balance -= amount
            to_account.balance += amount

    def send_external(self, from_account, to_address, amount, label):
        """ Create a new external transaction and put it to the transaction queue.

        The transaction is not send until `broadcast()` is called
        for this wallet.

        :return: Transaction object
        """
        session = Session.object_session(self)

        assert session
        assert from_account.wallet == self.id

        # TODO: Currently we don't allow
        # negative withdrawals on external sends

        if from_account.balance < amount:
            raise NotEnoughAccountBalance()

        with from_account.lock(), self.lock():

            transaction = self.Transaction()
            transaction.sending_account = from_account.id
            transaction.amount = amount
            transaction.state = "pending"
            transaction.wallet = self.id
            transaction.address = to_address
            session.add(transaction)

            from_account.balance -= amount
            self.balance -= amount

    def broadcast(self):
        """ Broadcast all pending external send transactions.

        This is desgined to be run from a background task,
        as this might be blocking operation or the backend connection might be down.
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
                outgoing[tx.address] += tx.amount

            if outgoing:
                txid = self.backend.send(outgoing)
                txs.update(dict(state="broadcasted", broadcasted_at=_now(), txid=txid))

    def refresh_total_balance(self):
        """ Make the balance to match with the actual backend.

        This is only useful for send_external() balance checks.
        Actual address balances will be out of sync after calling this
        (if the balance is incorrect).
        """
        self.balance = self.backend.get_balance()

    def receive(self, receiver, amount):
        """
        :return: (account, total balance) tuple
        """
        pass