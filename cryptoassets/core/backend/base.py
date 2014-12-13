"""

    Base classes for cryptocurrency backend.

"""

import abc


class CoinBackend(abc.ABC):
    """ Cryptocurrency management backend.

    Provide necessecities for low-level cryptocurrency usage, like creating wallets, addresses, sending and receiving the currency.

    Manage communications with the cryptocurrency network. The commucications can be done either by API service (block.io, blockchain.info) or raw protocol daemon (bitcoind).

    The accounting amounts are in the integer amounts defined  by the datbase models, e.g. satoshis for Bitcoin. If the backend supplies amounts in different unit, they most be converted  forth and back by the backend. For the example, see :py:class:`cryptoassets.core.backend.blockio`.
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
    def get_lock(self, name):
        """ Create a named lock to protect the operation. """

    @abc.abstractmethod
    def send(self, recipients):
        """Broadcast outgoing transaction.

        This is called by send/receive process.

        :param recipients: Dict of (address, internal amount)
        """

    @abc.abstractmethod
    def scan_addresses(self, addresses):
        """Give all known transactions to list of addresses.

        :param addresses: List of address strings

        :yield: Tuples of (txid, address, amount, confirmations)
        """

    def monitor_address(self, address):
        # XXX: Remove
        pass

    def setup_incoming_transactions(self, dbsession, notifiers):
        """Create a named pipe walletnotify handler.

        TODO: I feel this base class should be kept fully abstract and this method moved to an adapter or such.
        """

        from ..configure import ConfigurationError

        config = self.walletnotify_config

        if not config:
            return

        config = config.copy()

        transaction_updater = self.create_transaction_updater(dbsession, notifiers)

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
            raise ConfigurationError("Could not initialize backend {} with options {}".format(klass, data)) from te

        return handler


class IncomingTransactionRunnable(abc.ABC):
    """Backend specific thread/process taking care of accepting incoming transaction notifications from the network."""

    @abc.abstractmethod
    def start(self):
        pass

    @abc.abstractmethod
    def stop(self):
        pass



