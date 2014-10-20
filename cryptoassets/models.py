from abc import abstractmethod
import datetime

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


class NotEnoughBalance(Exception):
    """ Allow the balance to go to negative when sending. """


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


class GenericAccount(TableName, Base):
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


class GenericAddress(TableName, Base):
    __abstract__ = True
    id = Column(Integer, primary_key=True)
    address = Column(String(128))
    label = Column(String(255))
    balance = Column(Integer, default=0)
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

    @declared_attr
    def __tablename__(cls):
        return "{}_transaction".format(cls.coin)

    @declared_attr
    def address(cls):
        return Column(Integer, ForeignKey('{}_address.id'.format(cls.coin)))

    @declared_attr
    def wallet(cls):
        return Column(Integer, ForeignKey('{}_wallet.id'.format(cls.coin)))

    @declared_attr
    def sending_account(cls):
        return Column(Integer, ForeignKey('{}_account.id'.format(cls.coin)))

    @declared_attr
    def receiving_account(cls):
        return Column(Integer, ForeignKey('{}_account.id'.format(cls.coin)))

    amount = Column(Integer())
    status = Column('status', Enum('created', 'incoming', 'broadcasted', 'invalid', 'internal'))


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

    @declared_attr
    def __tablename__(cls):
        return "{}_wallet".format(cls.coin)

    @abstractmethod
    def _create_address(self):
        """ Allocates a new address for this wallet. """
        raise NotImplementedError()

    @abstractmethod
    def _create_account(self):
        """ Allocates a new address for this wallet. """
        raise NotImplementedError()

    def create_account(self, name):
        """
        """

        session = Session.object_session(self)

        assert session

        account = self._create_account()
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

        address = self._create_address()
        address.address = _address
        address.account = account.id
        address.label = label

        session.add(address)

        return address

    def send(self, account, receiving_address, amount):
        """
        :param account: The account owner from whose balance we
        """

    def import_address(self, account, label, address):
        """ Adds an external address under this wallet, under this account. """
        session = Session.object_session(self)
        _address = self.backend.create_address(label=label)
        address = self._create_address()
        address.address = _address
        address.account = account.id
        address.label = label
        address.refresh_balance()
        session.add(address)
        return address

    def send_internal(self, from_account, to_account, amount, label, allow_negative_balance=False):
        """
        """
        session = Session.object_session(self)

        assert from_account.wallet == self.id
        assert to_account.wallet == self.id
        assert session

        if not allow_negative_balance:
            if from_account.balance < amount:
                raise NotEnoughBalance()

        transaction = self._create_transaction()
        transaction.sending_account = from_account
        transaction.receiving_account = to_account
        transaction.amount = amount
        session.add(transaction)

        from_account.balance -= amount
        to_account.balance += amount

    def receive(self, receiver, amount):
        """
        :return: (account, total balance) tuple
        """
        pass

    def get_account_balance(self, account):
        """
        :return: True atomic balance of this wallet
        """

    def get_total_balance(self):
        """
        :return: Balance of all accounts in this wallet
        """

    def get_all_transactions(self):
        """
        :return: List of all transactions
        """

    def get_transactions(self, account):
        """
        :return: List of transactions
        """
