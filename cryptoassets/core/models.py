"""Base classes for SQL Alchemy models.

A set of abstract base classes which each cryptocurrency can inherit from.
Some special dependencies and hints need to be given for subclasses in order for
SQLAlchemy to be able to generate tables correctly.

See cryptoassets.coin modules for examples.
"""

import datetime
from collections import Counter
from decimal import Decimal

from sqlalchemy.sql import func
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


class BadAddress(Exception):
    """Cannot send to invalid address."""


class CannotCreateAddress(Exception):
    """Backend failed to create a new receiving address."""


class TableName:
    """Mix-in class to create database tables based on the coin description. """

    @declared_attr
    def __tablename__(cls):
        if not hasattr(cls, "coin_description"):
            # Abstract base class
            return None
        return cls.coin_description.name()


class CoinBackend:
    """Mix-in class to allow coin backend property on models."""

    #: Set by cryptoassets.app.CryptoassetsApp.setup_session
    backend = None


class CoinDescriptionModel(Base):
    """Base class for all cryptocurrency models."""

    __abstract__ = True

    #: Reference to :py:class:`cryptoassets.core.coin.registry.CoinDescription` which tells the relationships between this model and its counterparts in the system
    coin_description = None


class GenericAccount(CoinDescriptionModel, CoinBackend):
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
    balance = Column(Numeric(21, 8), default=0, nullable=False)

    def __init__(self):
        self.balance = 0

    @declared_attr
    def __tablename__(cls):
        return cls.coin_description.account_table_name

    @declared_attr
    def wallet_id(cls):
        return Column(Integer, ForeignKey('{}.id'.format(cls.coin_description.wallet_table_name)))

    @declared_attr
    def wallet(cls):
        return relationship(cls.coin_description.wallet_model_name, backref="accounts")

    def pick_next_receiving_address_label(self):
        """Generates a new receiving address label which is not taken yet.

        Some services, like block.io, requires all receiving addresses to have an unique label. We use this helper function in the situations where it is not meaningful to hand-generate labels every time.

        Generated labels are not user-readable, they are only useful for admin and accounting purposes.
        """
        session = Session.object_session(self)

        Address = self.coin_description.Address
        addresses = session.query(Address).filter(Address.account == self)
        friendly_date = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S")
        return "Receiving address #{} for account #{} created at {}".format(addresses.count()+1, self.id, friendly_date)

    def get_unconfirmed_balance(self):
        """Get the balance of this incoming transactions balance.

        TODO: Move to its own subclass

        TODO: Denormalize unconfirmed balances for faster look up?

        :return: Decimal
        """
        session = Session.object_session(self)

        Transaction = self.coin_description.Transaction
        NetworkTransaction = self.coin_description.NetworkTransaction
        Address = self.coin_description.Address
        Account = self.__class__

        unconfirmed_amount = func.sum(Transaction.amount).label("unconfirmed_amount")
        unconfirmed_amounts = session.query(unconfirmed_amount).join(NetworkTransaction).filter(NetworkTransaction.confirmations < NetworkTransaction.confirmation_count).join(Address).filter(Address.account == self)

        results = unconfirmed_amounts.all()
        assert len(results) == 1
        # SQL might spit out None if no matching rows
        return results[0][0] or Decimal(0)

    def __str__(self):
        return "ACC:{} name:{} bal:{} wallet:{}".format(self.id, self.name, self.balance, self.wallet.id if self.wallet else "-")


class GenericAddress(CoinDescriptionModel):
    """ The base class for cryptocurrency addresses.

    The address can represent a

    * Receiving address in our system. In this case we have **account** set to non-NULL.

    * External address outside our system. In this **account** is set to NULL. This address has been referred in outgoing broadcast (XXX: subject to change)

    We can know about receiving addresses which are addresses without our system where somebody can deposit cryptocurrency. We also know about outgoing addresses where somebody has sent cryptocurrency from our system. For outgoing addresses ``wallet`` reference is null.

    .. warning::

        Some backends (block.io) enforce that receiving address labels must be unique across the system. Other's don't.
        Just bear this in mind when creating address labels. E.g. suffix them with a timetamp to make them more unique.

    """
    __abstract__ = True

    #: Running counter used in foreign key references
    id = Column(Integer, primary_key=True)

    #: The string presenting the address label in the network
    address = Column(String(127), nullable=False)

    #: Human-readable label for this address. User for the transaction history listing of the user.
    label = Column(String(255))

    #: Received balance of this address. Only *confirmed* deposits count, filtered by GenericConfirmationTransaction.confirmations. For getting other balances, check ``get_balance_by_confirmations()``.
    #: NOTE: Numeric Accuracy checked for Bitcoin only ATM
    balance = Column(Numeric(21, 8), default=0, nullable=False)
    created_at = Column(DateTime, default=_now)
    updated_at = Column(DateTime, onupdate=_now)

    #: Archived addresses are no longer in active incoming transaction polling
    #: and may not appear in the user wallet list
    archived_at = Column(DateTime, default=None, nullable=True)

    @declared_attr
    def __tablename__(cls):
        return cls.coin_description.address_table_name

    @declared_attr
    def account_id(cls):
        assert cls.coin_description.account_table_name
        return Column(Integer, ForeignKey(cls.coin_description.account_table_name + ".id"))

    def is_deposit(self):
        return self.account is not None

    #: If account is set to nul then this is an external address
    @declared_attr
    def account(cls):
        """The owner account of this receiving addresses.

        This is None if the address is not a receiving addresses, but only exists in the network, outside our system.
        """
        assert cls.coin_description.account_model_name
        return relationship(cls.coin_description.account_model_name, backref="addresses")

    def get_received_transactions(self, external=True, internal=True):
        """Get all transactions this address have received, both internal and external deposits."""
        session = Session.object_session(self)
        Transaction = self.coin_description.Transaction

        q_internal = session.query(Transaction).filter(Transaction.sending_account != None, Transaction.receiving_account == self)  # noqa

        q_external = session.query(Transaction).filter(Transaction.network_transaction != None, Transaction.address == self)  # noqa

        if internal and external:
            return q_internal.union(q_external)
        elif internal:
            return q_internal
        elif external:
            return q_external
        else:
            return None

    def get_balance_by_confirmations(self, confirmations=0, include_internal=True):
        """Calculates address's received balance of all arrived incoming transactions where confirmation count threshold is met.

        By default confirmations is zero, so we get unconfirmed balance.

        .. note ::

            This is all time received balance, not balance left after spending.

        TODO: Move to its own subclass

        :param confirmations: Confirmation count as threshold
        """
        total = 0

        for t in self.get_received_transactions():
            if t.network_transaction:
                if t.network_transaction.confirmations >= confirmations:
                    total += t.amount
            elif t.state == "internal":
                assert t.receiving_account == self
                total += t.amount
            else:
                raise RuntimeError("Cannot handle tx {}".format(t))

        return total

    @declared_attr
    def __table_args__(cls):
        return (UniqueConstraint('account_id', 'address', name='_account_address_uc'),)

    def __str__(self):
        return "Addr:{} [{}] deposit:{} account:{} balance:{} label:{} updated:{}".format(self.id, self.address, self.is_deposit(), self.account and self.account.id or "-", self.balance, self.label, self.updated_at)


class GenericTransaction(CoinDescriptionModel):
    """A transaction between accounts, incoming transaction or outgoing transaction.

    Transactions can be classified as following:

    * Deposit: Incoming, external, transaction from cryptocurrency network.

        * Has ``network_transaction`` set.

        * Has ``receiving_account`` set.

        * No ``sending_account``

    * Broadcast: Outgoign, external, transaction to cryptocurrency network.

        * Has ``network_transaction`` set.

        * Has ``receiving_account`` set.

        * No ``receiving_account``

    * Internal transactions

        * Which are not visible outside our system.

        * have both ``sending_account`` and ``receiving_account`` set.

        * ``network_transaction`` is null

        * Internal transactions can be further classified as: ``ìnternal`` (normal between accounts), ``balance_import`` (initial wallet import to system) and ``network_fee`` (fees accounted to the network fee account when transaction was broadcasted)

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
    state = Column(Enum('pending', 'broadcasted', 'incoming', 'processed', 'internal', 'network_fee', 'balance_import', name="transaction_state"), nullable=False)

    #: Human readable label what this transaction is all about.
    #: Must be unique for each account
    label = Column(String(255), nullable=True)

    # Dynamically generated attributes based on the coin name

    @declared_attr
    def __tablename__(cls):
        return cls.coin_description.transaction_table_name

    @declared_attr
    def wallet_id(cls):
        return Column(Integer, ForeignKey(cls.coin_description.wallet_table_name + ".id"), nullable=False)

    @declared_attr
    def address_id(cls):
        return Column(Integer, ForeignKey(cls.coin_description.address_table_name + ".id"), nullable=True)

    @declared_attr
    def sending_account_id(cls):
        return Column(Integer, ForeignKey(cls.coin_description.account_table_name + ".id"))

    @declared_attr
    def receiving_account_id(cls):
        return Column(Integer, ForeignKey(cls.coin_description.account_table_name + ".id"))

    @declared_attr
    def network_transaction_id(cls):
        return Column(Integer, ForeignKey(cls.coin_description.network_transaction_table_name + ".id"))

    @declared_attr
    def address(cls):
        """ External cryptocurrency network address associated with the transaction.

        For outgoing transactions this is the walletless Address object holding only
        the address string.

        For incoming transactions this is the Address object with the reference
        to the Account object who we credited for this transfer.
        """
        return relationship(cls.coin_description.address_model_name,  # noqa
            primaryjoin="{}.address_id == {}.id".format(cls.__name__, cls.coin_description.address_model_name),
            backref="transactions")

    @declared_attr
    def sending_account(cls):
        """ The account where the payment was made from.
        """
        return relationship(cls.coin_description.account_model_name,  # noqa
            primaryjoin="{}.sending_account_id == {}.id".format(cls.__name__, cls.coin_description.account_model_name),
            backref="sent_transactions")

    @declared_attr
    def receiving_account(cls):
        """ The account which received the payment.
        """
        return relationship(cls.coin_description.account_model_name,  # noqa
            primaryjoin="{}.receiving_account_id == {}.id".format(cls.__name__, cls.coin_description.account_model_name),
            backref="received_transactions")

    @declared_attr
    def network_transaction(cls):
        """Associated cryptocurrency network transaction.
        """
        return relationship(cls.coin_description.network_transaction_model_name,  # noqa
            primaryjoin="{}.network_transaction_id == {}.id".format(cls.__name__, cls.coin_description.network_transaction_model_name),
            backref="transactions")

    @declared_attr
    def wallet(cls):
        """ Which Wallet object contains this transaction.
        """
        return relationship(cls.coin_description.wallet_model_name, backref="transactions")

    def can_be_confirmed(self):
        """ Return if the transaction can be considered as final.
        """
        return True

    @property
    def txid(self):
        """Return txid of associated network transaction (if any).

        Shortcut for ``self.network_transaction.txid``.
        """
        if self.network_transaction:
            return self.network_transaction.txid
        return None

    def __str__(self):
        # TODO: Move confirmations part to subclass
        return "TX:{} state:{} txid:{} sending acco:{} receiving acco:{} amount:{}, confirms:{}".format(self.id, self.state, self.txid, self.sending_account and self.sending_account.id, self.receiving_account and self.receiving_account.id, self.amount, getattr(self, "confirmations", "-"))


class GenericConfirmationTransaction(GenericTransaction):
    """Mined transaction which receives "confirmations" from miners in blockchain.

    This works in pair with :py:class:`cryptoassets.core.models.GenericConfirmationNetworkTransaction`. :py:class`GenericConfirmationTransaction` has logic to decide when the incoming transaction is final and the balance in the coming transaction appears credited on :py:class:`cryptoassets.core.models.GenericAccount`.
    """

    __abstract__ = True

    #: How many confirmations to wait until the deposit is set as credited.
    #: TODO: Make this configurable.
    confirmation_count = 3

    def can_be_confirmed(self):
        """Does this transaction have enough confirmations it could be confirmed by our standards."""
        return self.confirmations >= self.confirmation_count

    @property
    def confirmations(self):
        """Get number of confirmations the incoming NetworkTransaction has.

        .. note::

            Currently confirmations count supported only for deposit transactions.

        :return: -1 if the confirmation count is not available
        """

        # -1 was chosen instead of none to make confirmation count easier

        ntx = self.network_transaction
        if ntx is None:
            return -1

        if ntx.confirmations is None:
            return -1

        assert ntx
        assert isinstance(ntx, GenericConfirmationNetworkTransaction)
        return ntx.confirmations


class GenericWallet(CoinDescriptionModel, CoinBackend):
    """ A generic wallet implemetation.

    Inside the wallet there is a number of accounts.

    We support internal transaction between the accounts of the same wallet as off-chain transactions. If you call ``send()``for the address which is managed by the same wallet, an internal transaction is created by ``send_internal()``.
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

    @declared_attr
    def __tablename__(cls):
        return cls.coin_description.wallet_table_name

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

        account = self.coin_description.Account()
        account.name = name
        account.wallet = self
        session.add(account)
        return account

    def get_account_by_name(self, name):
        session = Session.object_session(self)
        instance = session.query(self.coin_description.Account).filter_by(name=name).first()
        return instance

    def get_or_create_account_by_name(self, name):
        session = Session.object_session(self)

        instance = session.query(self.coin_description.Account).filter_by(name=name).first()
        if not instance:
            instance = self.create_account(name)

        return instance

    def get_or_create_network_fee_account(self):
        """Lazily create the special account where we account all network fees.

        This is for internal bookkeeping only. These fees MAY be
        charged from the users doing the actual transaction, but it
        must be solved on the application level.
        """
        return self.get_or_create_account_by_name(self.coin_description.Account.NETWORK_FEE_ACCOUNT)

    def create_receiving_address(self, account, label=None, automatic_label=False):
        """ Creates a new receiving address.

        All incoming transactions on this address are put on the given account.

        The notifications for transctions to the address might not be immediately available after the address creation depending on the backend. For example, with block.io you need to wait some seconds before it is safe to send anything to the address if you wish to receive the wallet notification.

        :param account: GenericAccount object

        :param label: Label for this address - must be human-readable

        :return: GenericAddress object
        """

        session = Session.object_session(self)

        assert session
        assert account
        assert account.id

        assert label or automatic_label, "You must give explicit label for the address or use automatic_label option"

        if not label and automatic_label:
            label = account.pick_next_receiving_address_label()

        try:
            _address = self.backend.create_address(label=label)
        except Exception as e:
            raise CannotCreateAddress("Backend failed to create address for account {} label {}".format(account.id, label)) from e

        address = self.coin_description.Address()
        address.address = _address
        address.account = account
        address.label = label
        address.wallet = self

        session.add(address)

        return address

    def get_or_create_external_address(self, address):
        """ Create an accounting entry for an address which is outside our system.

        When we send out external transactions, they go to these address entries.
        These addresses do not have wallet or account connected to our system.

        :param address: Address as a string
        """

        assert type(address) == str

        session = Session.object_session(self)

        _address = session.query(self.coin_description.Address).filter_by(address=address, account_id=None).first()
        if not _address:
            _address = self.coin_description.Address()
            _address.address = address
            _address.account = None
            _address.label = "External {}".format(address)
            session.add(_address)

        return _address

    def send(self, from_account, receiving_address, amount, label, force_external=False, testnet=False):
        """Send the amount of cryptocurrency to the target address.

        If the address is hosted in the same wallet do the internal send with :py:meth:`cryptoassets.core.models.GenericWallet.send_internal`,  otherwise go through the public blockchain with :py:meth:`cryptoassets.core.models.GenericWallet.send_external`.

        :param from_account: The account owner from whose balance we

        :param receiving_address: Receiving address as a string

        :param amount: Instance of `Decimal`

        :param label: Recorded text to the sending wallet

        :param testnet: Assume the address is testnet address. Currently not used, but might affect address validation in the future.

        :param force_external: Set to true to force the transaction go through the network even if the target address is in our system.

        :return: Transaction object
        """
        session = Session.object_session(self)

        assert isinstance(from_account, self.coin_description.Account)
        assert type(receiving_address) == str
        assert isinstance(amount, Decimal)

        # TODO: Check minimal withdrawal amount

        Address = self.coin_description.Address

        internal_receiving_address = session.query(Address).filter(Address.address == receiving_address, Address.account != None).first()  # noqa

        if internal_receiving_address and not force_external:
            to_account = internal_receiving_address.account
            return self.send_internal(from_account, to_account, amount, label)
        else:
            return self.send_external(from_account, receiving_address, amount, label)

    def add_address(self, account, label, address):
        """ Adds an external address under this wallet, under this account.

        There shouldn't be reason to call this directly, unless it is for testing purposes.

        :param account: Account instance

        :param address: Address instance
        """
        session = Session.object_session(self)

        assert session, "Tried to add address to a non-bound wallet object"

        address_obj = self.coin_description.Address()
        address_obj.address = address
        address_obj.account = account
        address_obj.label = label
        session.add(address_obj)
        return address_obj

    def get_accounts(self):
        session = Session.object_session(self)
        # Go through all accounts and all their addresses

        return session.query(self.coin_description.Account).filter(self.coin_description.Account.wallet_id == self.id)  # noqa

    def get_account_by_address(self, address):
        """Check if a particular address belongs to receiving address of this wallet and return its account.

        This does not consider bitcoin change addresses and such.

        :return: Account instance or None if the wallet doesn't know about the address
        """
        session = Session.object_session(self)
        addresses = session.query(self.coin_description.Address).filter(self.coin_description.Address.address == address).join(self.coin_description.Account).filter(self.coin_description.Account.wallet_id == self.id)  # noqa
        _address = addresses.first()
        if _address:
            return _address.account
        return None

    def get_pending_outgoing_transactions(self):
        """Get the list of outgoing transactions which have not been associated with any broadcast yet."""

        session = Session.object_session(self)
        Transaction = self.coin_description.Transaction
        txs = session.query(Transaction).filter(Transaction.state == "pending", Transaction.receiving_account == None, Transaction.network_transaction == None)  # noqa
        return txs

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
        return session.query(self.coin_description.Address).filter(self.coin_description.Address.archived_at == None).join(self.coin_description.Account).filter(self.coin_description.Account.wallet_id == self.id)  # noqa

    def get_deposit_transactions(self):
        """Get all deposit transactions to this wallet.

        These are external incoming transactions, both unconfirmed and confirmed.

        :return: SQLAlchemy query of Transaction model
        """

        session = Session.object_session(self)

        # Go through all accounts and all their addresses
        # XXX: Make state handling more robust
        Transaction = self.coin_description.Transaction
        NetworkTransaction = self.coin_description.NetworkTransaction

        return session.query(Transaction).filter(Transaction.wallet == self).filter(Transaction.network_transaction_id != None).join(NetworkTransaction).filter(NetworkTransaction.transaction_type == "deposit")  # noqa

    def get_active_external_received_transcations(self):
        """Return unconfirmed transactions which are still pending the network confirmations to be credited.

        :return: SQLAlchemy query of Transaction model
        """
        Transaction = self.coin_description.Transaction
        deposits = self.get_deposit_transactions()
        return deposits.filter(Transaction.credited_at == None)  # noqa

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

        addresses = session.query(self.coin_description.Address).filter(self.coin_description.Address.account == account).values("address")

        total_balance = 0

        # The backend might do exists checks using in operator
        # to this, we cannot pass generator, thus list()
        for address, balance in self.backend.get_balances(list(item.address for item in addresses)):
            total_balance += balance
            session.query(self.coin_description.Address).filter(self.coin_description.Address.address == address).update({"balance": balance})

        account.balance = total_balance

    def send_internal(self, from_account, to_account, amount, label, allow_negative_balance=False):
        """ Tranfer currency internally between the accounts of this wallet.

        :param from_account: GenericAccount

        :param to_account: GenericAccount

        :param amount: The amount to transfer in wallet book keeping unit
        """
        session = Session.object_session(self)

        assert from_account
        assert to_account

        assert from_account.wallet == self
        assert to_account.wallet == self
        # Cannot do internal transactions within the account
        assert from_account.id
        assert to_account.id

        assert isinstance(amount, Decimal)

        if from_account.id == to_account.id:
            raise SameAccount("Transaction receiving and sending internal account is same: #{}".format(from_account.id))

        if not allow_negative_balance:
            if from_account.balance < amount:
                raise NotEnoughAccountBalance("Cannot send, needs {} account balance is {}", amount, from_account.balance)

        transaction = self.coin_description.Transaction()
        transaction.sending_account = from_account
        transaction.receiving_account = to_account
        transaction.amount = amount
        transaction.wallet = self
        transaction.credited_at = _now()
        transaction.label = label
        transaction.state = "internal"
        session.add(transaction)

        from_account.balance -= amount
        to_account.balance += amount

        return transaction

    def send_external(self, from_account, to_address, amount, label, testnet=False):
        """Create a new external transaction and put it to the transaction queue.

        When you send cryptocurrency out from the wallet, the transaction is put to the outgoing queue. Only after you broadcast has been performed (:py:mod:`cryptoassets.core.tools.broadcast`) the transaction is send out to the network. This is to guarantee the system responsiveness and fault-tolerance, so that outgoing transactions are created even if we have temporarily lost the connection with the cryptocurrency network. Broadcasting is usually handled by *cryptoassets helper service*.

        :param from_account: Instance of :py:class:`cryptoassets.core.models.GenericAccount`

        :param to_address: Address as a string

        :param amount: Instance of `Decimal`

        :param label: Recorded to the sending wallet history

        :param testnet: to_address is a testnet address

        :return: Instance of :py:class:`cryptoassets.core.models.GenericTransaction`
        """
        session = Session.object_session(self)

        assert session
        assert from_account.wallet == self

        if not self.coin_description.address_validator.validate_address(to_address, testnet):
            raise BadAddress("Cannot send to address {}".format(to_address))

        # TODO: Currently we don't allow
        # negative withdrawals on external sends
        #
        if from_account.balance < amount:
            raise NotEnoughAccountBalance()

        _address = self.get_or_create_external_address(to_address)

        transaction = self.coin_description.Transaction()
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

    def charge_network_fees(self, broadcast, fee):
        """Account network fees due to transaction broadcast.

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

        transaction = self.coin_description.Transaction()
        transaction.sending_account = fee_account
        transaction.receiving_account = None
        transaction.amount = fee
        transaction.state = "network_fee"
        transaction.wallet = self
        transaction.label = "Network fees for {}".format(broadcast.txid)

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

    def deposit(self, ntx, address, amount, extra=None):
        """Informs the wallet updates regarding external incoming transction.

        This method should be called by the coin backend only.

        Write the transaction to the database.
        Notify the application of the new transaction status.
        Wait for the application to mark the transaction as processed.

        Note that we may receive the transaction many times with different confirmation counts.

        :param ntx: Associated :py:class:`cryptoassets.core.models.NetworkTransaction`

        :param address: Address as a string

        :param amount: Int, as the basic currency unit

        :param extra: Extra variables to set on the transaction object as a dictionary. (Currently not used)

        :return: tuple (Account instance, new or existing Transaction object, credited boolean)
        """

        session = Session.object_session(self)

        assert self.id
        assert amount > 0, "Receiving transaction to {} with amount {}".format(address, amount)
        assert ntx
        assert ntx.id
        assert type(address) == str

        _address = session.query(self.coin_description.Address).filter(self.coin_description.Address.address == address).first()  # noqa

        assert _address, "Wallet {} does not have address {}".format(self.id, address)
        assert _address.id

        # TODO: Have something smarter here after we use relationships
        account = session.query(self.coin_description.Account).filter(self.coin_description.Account.id == _address.account_id).first()  # noqa
        assert account.wallet == self

        # Check if we already have this transaction
        Transaction = self.coin_description.Transaction
        transaction = session.query(Transaction).filter(Transaction.network_transaction_id == ntx.id, self.coin_description.Transaction.address_id == _address.id).first()

        if not transaction:
            # We have not seen this transaction before in the database
            transaction = self.coin_description.Transaction()
            transaction.network_transaction = ntx
            transaction.address = _address
            transaction.state = "incoming"
            transaction.wallet = self
            transaction.amount = amount
        else:
            assert transaction.state in ("incoming", "credited")
            assert transaction.sending_account is None

        transaction.sending_account = None
        transaction.receiving_account = account
        session.add(transaction)

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
        transactions = session.query(self.coin_description.Transaction.id, self.coin_description.Transaction.state).filter(self.coin_description.Transaction.id == transaction_id, self.coin_description.Transaction.state == "incoming")  # noqa

        # We should mark one and only one transaction processed
        assert transactions.count() == 1

        transactions.update(dict(state="processed", processed_at=_now()))


class GenericNetworkTransaction(CoinDescriptionModel):
    """A transaction in cryptocurrencty networkwhich is concern of our system.

    External transactions can be classified as

    * Deposits: incoming transactions to our receiving addresses

    * Broadcasts: we are sending out currency to the network

    If our intenal transaction (:py:class:`cryptoassets.core.models.Transaction`) has associated network transaction, it's ``transaction.network_transaction`` reference is set. Otherwise transactions are internal transactions and not visible in blockchain.

    .. note ::

        NetworkTransaction does not have reference to wallet. One network transaction may contain transfers to many wallets.

    **Handling incoming deposit transactions**

    For more information see :py:mod:`cryptoassets.core.backend.transactionupdater` and :py:mod:`cryptoassets.core.tools.confirmationupdate`.

    **Broadcasting outgoing transactions**

    Broadcast constructs an network transaction and bundles any number of outgoing pending transactions to it. During the broadcast, one can freely bundle transactions together to lower the network fees, or mix transactions for additional privacy.

    Broadcasts are constructed by Cryptoassets helper service which will periodically scan for outgoing transactions and construct broadcasts of them. After constructing, broadcasting is attempted. If the backend, for a reason or another, fails to make a broadcast then this broadcast is marked as open and must be manually vetted to succeeded or failed.

    For more information see :py:mod:`cryptoassets.core.tools.broadcast`.
    """

    __abstract__ = True

    #: Running counter used in foreign key references
    id = Column(Integer, primary_key=True)

    #: When this transaction become visible in our database
    created_at = Column(DateTime, default=_now)

    #: Network transaction has associated with this transaction.
    #: E.g. Bitcoin transaction hash.
    txid = Column(String(255), nullable=True)

    #: Is this transaction incoming or outgoing from our system
    transaction_type = Column(Enum('deposit', 'broadcast', name="network_transaction_type"), nullable=False)

    state = Column(Enum('incoming', 'credited', 'pending', 'broadcasted', name="network_transaction_state"), nullable=False)

    #: When broadcast was marked as outgoing
    opened_at = Column(DateTime)

    #: When broadcast was marked as sent
    closed_at = Column(DateTime)

    @declared_attr
    def __tablename__(cls):
        return cls.coin_description.network_transaction_table_name

    @declared_attr
    def __table_args__(cls):
        """Each txid can appear twice, once for deposit once for broadcast. """
        return (UniqueConstraint('transaction_type', 'txid', name='_transaction_type_txid_uc'),)

    def __str__(self):
        return "NTX:{} type:{} state:{} txid:{} opened_at:{} closed_at:{}".format(self.id, self.transaction_type, self.state, self.txid, self.opened_at, self.closed_at)

    @classmethod
    def get_or_create_deposit(cls, session, txid):
        """Get a hold of incoming transaction.

        :return: tuple(Instance of :py:class:`cryptoassets.core.models.GenericNetworkTransaction`., bool created)
        """
        NetworkTransaction = cls
        instance = session.query(NetworkTransaction).filter_by(transaction_type="deposit", txid=txid).first()

        if not instance:
            instance = NetworkTransaction()
            instance.txid = txid
            instance.transaction_type = "deposit"
            instance.state = "incoming"
            session.add(instance)
            return instance, True
        else:
            return instance, False


class GenericConfirmationNetworkTransaction(GenericNetworkTransaction):
    """Mined transaction which receives "confirmations" from miners in blockchain.

    This is a subtype of ``GenericNetworkTransaction`` with confirmation counting abilities.
    """
    __abstract__ = True

    #: How many miner confirmations this tx has received. The value is ``-1`` until the transaction is succesfully broadcasted, after which is it ``0``
    confirmations = Column(Integer, nullable=False, default=-1)

    #: How many confirmations to wait until the transaction is set as confirmed.
    #: TODO: Make this configurable.
    confirmation_count = 3

    def can_be_confirmed(self):
        """ Does this transaction have enough confirmations it could be confirmed by our standards. """
        return self.confirmations >= self.confirmation_count

    def __str__(self):
        return "NTX:{} type:{} state:{} txid:{} confirmations:{}, opened_at:{} closed_at:{}".format(self.id, self.transaction_type, self.state, self.txid, self.confirmations, self.opened_at, self.closed_at)
