"""

    TODO:

    - Define SQLAlchemy relationships properly - http://docs.sqlalchemy.org/en/rel_0_9/orm/tutorial.html#building-a-relationship
      Some challenges with all those declared_attrs() flying around.

"""

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
    DateTime,
    ForeignKey,
    Enum,
    )

from sqlalchemy.orm.session import Session
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy.orm.exc import NoResultFound

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


class SameAccount(Exception):
    """ Cannot do internal transaction within the same account.

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
    def wallet(cls):
        return Column(Integer, ForeignKey('{}_wallet.id'.format(cls.coin)))

    def lock(self):
        """ Get a lock context manager to protect operations targeting this account.

        This lock must be acquired for all operations touching the balance.
        """
        return self.backend.get_lock("{}_account_lock_{}".format(self.coin, self.id))


class GenericConfirmationAccount(GenericAccount):
    """ Account subtype which has a confirmation level for incoming transactions. """
    __abstract__ = True
    confirmations_required_on_receive = Column(Integer)

    #: Confirmations needed to credit this transaction
    #: on the receiving account
    confirmation_count = 3

    def is_confirmed(self):
        return self.confirmations > self.confirmation_count


class GenericAddress(TableName, Base):
    __abstract__ = True
    id = Column(Integer, primary_key=True)
    address = Column(String(128), nullable=False, unique=True)
    label = Column(String(255), unique=True)
    balance = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime, default=_now)
    updated_at = Column(DateTime, onupdate=_now)
    archived_at = Column(DateTime, default=None, nullable=True)

    @declared_attr
    def __tablename__(cls):
        return "{}_address".format(cls.coin)

    @declared_attr
    def account(cls):
        return Column(Integer, ForeignKey('{}_account.id'.format(cls.coin)), nullable=False)


class GenericTransaction(TableName, Base):
    """
    """
    __abstract__ = True
    id = Column(Integer, primary_key=True)
    created_at = Column(DateTime, default=_now)
    credited_at = Column(DateTime, nullable=True, default=None)
    processed_at = Column(DateTime, nullable=True, default=None)
    amount = Column(Integer())
    state = Column(Enum('pending', 'broadcasted', 'incoming', 'processed', 'internal', 'network_fee'))
    label = Column(String(255), nullable=True)
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

    def is_confirmed(self):
        return True


class GenericConfirmationTransaction(GenericTransaction):
    __abstract__ = True
    confirmations = Column(Integer)

    #: Confirmations needed to credit this transaction
    #: on the receiving account
    confirmation_count = 0

    def is_confirmed(self):
        return self.confirmations > self.confirmation_count


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
        """
        """

        session = Session.object_session(self)

        assert session
        assert self.id, "Flush DB transaction for wallet before trying to add accounts to it"

        account = self.Account()
        account.name = name
        account.wallet = self.id
        session.add(account)
        return account

    def get_or_create_network_fee_account(self):
        """ Create a special account where we account all network fees.

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
        """ Creates private/public key pair for receiving.
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
            address.account = account.id
            address.label = label
            address.wallet = self.id

            session.add(address)

            # Make sure the address is written to db
            # before we can make any entires of received
            # transaction on it in monitoring
            session.flush()

        self.backend.monitor_address(address)

        return address

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

        """
        session = Session.object_session(self)
        address_obj = self.Address()
        address_obj.address = address
        address_obj.account = account.id
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

        return session.query(self.Account).filter(self.Account.wallet == self.id)  # noqa

    def get_receiving_addresses(self, expired=False):
        """ Get all receiving addresses for this wallet.

        This is mostly used by the backend to get the list
        of receiving addresses to monitor for incoming transactions
        on the startup.

        :param expired: Include expired addresses
        """

        session = Session.object_session(self)

        # Go through all accounts and all their addresses
        return session.query(self.Address).filter(self.Address.archived_at is not None).join(self.Account).filter(self.Account.wallet == self.id)

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
        assert session

        if from_account.id == to_account.id:
            raise SameAccount("Trying to do internal transfer on account id {}".format(from_account.id))

        with from_account.lock(), to_account.lock():

            if not allow_negative_balance:
                if from_account.balance < amount:
                    raise NotEnoughAccountBalance()

            transaction = self.Transaction()
            transaction.sending_account = from_account.id
            transaction.receiving_account = to_account.id
            transaction.amount = amount
            transaction.wallet = self.id
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

        :return: Transaction object
        """
        session = Session.object_session(self)

        assert session
        assert from_account.wallet == self.id

        with from_account.lock(), self.lock():

            # TODO: Currently we don't allow
            # negative withdrawals on external sends
            #
            if from_account.balance < amount:
                raise NotEnoughAccountBalance()

            transaction = self.Transaction()
            transaction.sending_account = from_account.id
            transaction.amount = amount
            transaction.state = "pending"
            transaction.wallet = self.id
            transaction.address = to_address
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
                outgoing[tx.address] += tx.amount

            if outgoing:
                txid, fee = self.backend.send(outgoing)
                assert txid
                txs.update(dict(state="broadcasted", processed_at=_now(), txid=txid))

                if fee:
                    self.charge_network_fees(txs, txid, fee)

        return len(outgoing)

    def charge_network_fees(self, txs, txid, fee):
        """ Divide the network fees for all transaction participants.

        By default this just creates a new accounting entry on a special account
        where network fees is put.

        :param txs: Internal transactions participating in send

        :param txid: External transaction id

        :param fee: Fee as the integer
        """

        session = Session.object_session(self)

        fee_account = self.get_or_create_network_fee_account()

        transaction = self.Transaction()
        transaction.sending_account = fee_account.id
        transaction.receiving_account = None
        transaction.amount = fee
        transaction.state = "network_fee"
        transaction.wallet = self.id
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
        """ The backend informs us a new transaction has arrived.

        Write the transaction to the database.
        Notify the application of the new transaction status.
        Wait for the application to mark the transaction as processed.

        Note that we may receive the transaction many times with different confirmation counts.

        :param txid: External transaction id

        :param address: Address as a string

        :param amount: Int, as the basic currency unit

        :param extra: Extra variables to set on the transaction, like confirmation count.

        :return: new Transaction object
        """

        session = Session.object_session(self)

        assert self.id
        assert amount > 0
        assert txid

        _address = session.query(self.Address).filter(self.Address.address == address).first()  # noqa

        assert _address, "Wallet {} does not have address {}".format(self.id, address)
        assert _address.id

        # TODO: Have something smarter here after we use relationships
        account = session.query(self.Account).filter(self.Account.id == _address.account).first()  # noqa
        assert account.wallet == self.id

        # Check if we already have this transaction
        transaction = session.query(self.Transaction).filter(self.Transaction.txid == txid, self.Transaction.address == _address.id).first()
        if not transaction:
            # We have not seen this transaction before in the database
            transaction = self.Transaction()
            transaction.txid = txid
            transaction.address = _address.id
            transaction.state = "incoming"
            transaction.wallet = self.id
            transaction.amount = amount
            session.add(transaction)

        transaction.sending_account = None
        transaction.receiving_account = account.id

        # Copy extra transaction payload
        if extra:
            for key, value in extra.items():
                setattr(transaction, key, value)

        if transaction.is_confirmed() and not transaction.credited_at:

            # Consider this transaction to be confirmed and update the receiving account
            transaction.credited_at = _now()

            with account.lock():
                account.balance += transaction.amount

            with self.lock():
                self.balance += transaction.amount

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
