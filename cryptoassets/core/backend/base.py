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
    def setup_incoming_transactions(self, dbsession):
        """Setup incoming tranasction handler.

        This is called by cryptoassets helper service. When the service is starting, create necessary files, scripts, HTTP ports, etc. to receive notifications from the backend service. E.g. in the case of bitcoind this sets up ``walletnotify`` handler, so that when bitcoind sees a tranaction our hook is called.

        :param dbsession: SQLAlchemy database session used to update the database for incoming transactions.

        :return: A runnable object with `start()` and `stop()` methods (thread, process, etc.) or ``None`` if no runnable is needed
        """
