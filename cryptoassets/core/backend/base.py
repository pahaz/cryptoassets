"""Base classes for cryptocurrency backend."""

import abc

from zope.dottedname.resolve import resolve

from ..utils.conflictresolver import ConflictResolver
from ..event.registry import EventHandlerRegistry
from .transactionupdater import TransactionUpdater


class CoinBackend(abc.ABC):
    """ Cryptocurrency management backend.

    Provide necessecities for low-level cryptocurrency usage, like creating wallets, addresses, sending and receiving the currency.

    Manage communications with the cryptocurrency network. The commucications can be done either by API service (block.io, blockchain.info) or raw protocol daemon (bitcoind).

    The accounting amounts are in the integer amounts defined  by the datbase models, e.g. satoshis for Bitcoin. If the backend supplies amounts in different unit, they most be converted  forth and back by the backend. For the example, see :py:class:`cryptoassets.core.backend.blockio`.
    """

    def __init__(self):
        #: If ``track_incoming_confirmations`` is set to true, this is how many confirmations we track for each incoming transactions until we consider it "closed". Please note that this is API will most likely be changed in the future and this variable move to somewhere else.
        #: The variable is set by ``Configurator.setup_backend``.
        max_tracked_incoming_confirmations = None

    @abc.abstractmethod
    def require_tracking_incoming_confirmations(self):
        """Does this backend need to have some help to get incoming transaction confirmations tracked.

        Some daemons and walletnotify methods, namely bitcoind, only notify us back the first occurence of an incoming transactions. If we want to receive further confirmations from the transaction, we need to manually poll the transactions where our confirmation threshold is not yet met.

        Set this to true and the cryptoassets helper service will start a background job (:py:mod:`cryptoassets.core.tools.confirmationupdate` to keep receiving updates about the confirmations).

        :return: True or False
        """

    @abc.abstractmethod
    def create_address(self, label):
        """ Create a new receiving address.
        """

    @abc.abstractmethod
    def get_balances(self, addresses):
        """Get balances on multiple addresses.

        Return the address balance in the native format (backend converts to satoshis, etc.)

        :yield: (address, balance) tuples
        """

    @abc.abstractmethod
    def send(self, recipients):
        """Broadcast outgoing transaction.

        This is called by send/receive process.

        :param recipients: Dict of (address, internal amount)
        """

    @abc.abstractmethod
    def get_backend_balance(self):
        """Get full available hot wallet balance on the backend.

        May take backend-specific optional kwargs like ``confirmations``.

        This is used for :py:mod:`cryptoassets.core.tools.walletimport`.

        :return: Decimal
        """

    @abc.abstractmethod
    def list_received_transactions(self, extra):
        """List all received transactions the backend is aware off.

        :param extra: Dict of backend-specific optional arguments like ``dict(confirmations=0)``.

        :return: Instance of :py:class:`cryptoassets.core.backend.base.ListTransactionsIterator`.
        """

    def create_transaction_updater(self, conflict_resolver, event_handler_registry):
        """Create transaction updater to handle database writes with this backend.

        Creates :py:class:`cryptoassets.core.backend.transactionupdater.TransactionUpdater` instance.
        This TransactionUpdater is bound to this backend and provides safe APIs for doing broadcast and deposit updates.
        """
        tx_updater = TransactionUpdater(conflict_resolver, self, self.coin, event_handler_registry)
        return tx_updater

    def setup_incoming_transactions(self, conflict_resolver, event_handler_registry):
        """Configure the incoming transaction notifies from backend.

        The configuration for wallet notifies have been given to the backend earlier in the backend constructor. Now we read this configure, resolve the walletnotify handler class and instiate it.

        We'll hook into backend by creating ``cryptoassets.core.backend.transactionupdater.TransactionUpdater`` instance, which gets the list of event_handler_registry it needs to call on upcoming transaction.

        :param conflict_resolver: cryptoassets.core.utils.conflictresolver.ConflictResolver instance which is used to manage transactions

        :param event_handler_registry: :param event_handler_registry: :py:class`cryptoassets.core.event.registry.EventHandlerRegistry` instance or None if we don't want to notify of new transactions and just update the database

        :return: Instance of :py:class:`cryptoassets.core.backend.base.IncomingTransactionRunnable`
        """

        assert conflict_resolver, "Cannot setup incoming transactions without transaction conflict resolver in place"
        assert isinstance(conflict_resolver, ConflictResolver)
        assert isinstance(event_handler_registry, EventHandlerRegistry) or event_handler_registry is None

        config = self.walletnotify_config

        if not config:
            return

        config = config.copy()

        transaction_updater = self.create_transaction_updater(conflict_resolver, event_handler_registry)

        klass = config.pop("class")
        provider = resolve(klass)
        config["transaction_updater"] = transaction_updater
        # Pass given configuration options to the backend as is
        try:
            handler = provider(**config)
        except TypeError as te:
            # TODO: Here we reflect potential passwords from the configuration file
            # back to the terminal
            # TypeError: __init__() got an unexpected keyword argument 'network'
            raise RuntimeError("Could not initialize backend {} with options {}".format(klass, config)) from te

        return handler


class ListTransactionsIterator(abc.ABC):
    """Helper to iterate all transactions in the backend.

    Because different backends iterate to different directions, we abstract this away.

    .. note ::

        bitcoind iterates from index 0 with different batch sizes. block.io iterates from the latest transcation with fixed batch size of 100 and needs before txid parameter for the next batch.
    """

    def __init__(self, backend):
        """
        """
        self.backend = backend

    @abc.abstractmethod
    def fetch_next_txids():
        """Get next batch of transactions.

        txdata must be dict bitcoind-like format::

            {
                confirmations: 0,
                txid: "xxx",
                "details": {
                    "category": "received",
                    "amount": Decimal(1),
                    "address": "foobar"
                }
            }

        :return: List of next (txid, txdata) paits to iterate or empty list if iterating is done.
        """


class IncomingTransactionRunnable(abc.ABC):
    """Backend specific thread/process taking care of accepting incoming transaction notifications from the network."""

    @abc.abstractmethod
    def start(self):
        pass

    @abc.abstractmethod
    def stop(self):
        pass

    def register_new_addresses(self):
        """Backend has created new addresses and the incoming transcation monitor must know about them.

        Some monitoring systems need to refresh after new addresses have been added to the pool.
        """




