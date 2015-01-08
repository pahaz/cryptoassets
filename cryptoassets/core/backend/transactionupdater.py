import datetime
from collections import Counter
import logging

from sqlalchemy.orm.session import Session

from ..coin.registry import Coin
from ..notify.registry import NotifierRegistry
from ..notify import events

from ..utils.conflictresolver import ConflictResolver


logger = logging.getLogger(__name__)


class TransactionUpdater:
    """TransactionUpdater write transactions updates from API/backend to the database.

    TransactionUpdater uses :py:class:`cryptoassets.core.utils.conflictresolver.ConflictResolver` database transaction helper when updating transactions. This gives us guarantees that updates having possible db transaction conflicts are gracefully handled.

    The backend has hooked up some kind of wallet notify handler. The wallet notify handler uses TransactionUpdater to write updates of incoming transactoins to the database.

    TransactionUpdater is also responsible to fire any notification handlers to signal the cryptoassets client application to handle new transactions.

    TransactionUpdater is generally run inside :py:class:`cryptoassets.core.service.main.Server` process, as this process is responsible for all incoming transaction updates. No web or other front end should try to make their own updates.
    """

    def __init__(self, conflict_resolver, backend, coin, notifiers):
        """
        :param conflict_resolver: :py:class:`cryptoassets.core.utils.conflictresolver.ConflictResolver`

        :param backend: :py:class:`cryptoasets.core.backend.base.CoinBackend` instance

        :param coin: :py:class:`cryptoasets.core.coin.registry.Coin` instance

        :param notifiers: :py:class`cryptoassets.core.notify.registry.NotifierRegistry` instance
        """
        assert isinstance(coin, Coin)
        assert isinstance(conflict_resolver, ConflictResolver)

        self.backend = backend
        self.coin = coin
        self.conflict_resolver = conflict_resolver

        # Simple book-keeping of number of transactions we have handled
        self.count = 0

        #: UTC timestamp when we got the last transaction notification
        self.last_wallet_notify = None

        if notifiers:
            assert isinstance(notifiers, NotifierRegistry)
            #: Notifiers registry we are going to inform about transaction status updates
            self.notifiers = notifiers
        else:
            self.notifiers = None

        #: Diagnostics and bookkeeping statistics
        self.stats = Counter(network_transaction_updates=0, deposit_update=0)

    def _update_address_deposit(self, ntx, address, amount, confirmations):
        """Handle an incoming transaction update to a single address.

        TODO: confirmations is relevant for mined coins only. Abstract it away here.

        We received an update regarding cryptocurrency transaction ``txid``. This may be a new transaction we have not seen before or an existing transaction. If the transaction confirmation count is exceeded, the transaction is also marked as credited and account who this address belongs balance is topped up.

        ``handle_address_receive`` will write the updated data to the database. Relevant event handlers are fired (self.notifiers).

        Note that a single cryptocurrency transaction may contain updates to several addresses or several received sections to a single address.

        :return: tuple (Transaction id, boolean credited) for the Transaction object created/updated related to external txid
        """

        assert amount > 0

        session = Session.object_session(ntx)

        # Pass confirmations in the extra transaction details
        extra = dict(confirmations=confirmations)

        Address = self.coin.address_model

        address_obj = session.query(Address).filter(Address.address == address).first()  # noqa

        if address_obj:
            wallet = address_obj.account.wallet

            # Credit the account
            account, transaction = wallet.deposit(ntx, address, amount, extra)

            self.stats["deposit_updates"] += 1

            confirmations = transaction.confirmations

            logger.info("Wallet notify account %d, address %s, amount %s, tx confirmations %d", account.id, address, amount, confirmations)

            # This will cause Transaction instance to get transaction.id
            session.flush()

            return account.id, transaction.id, (transaction.credited_at is not None)

        else:
            logger.info("Skipping transaction notify for unknown address %s, amount %s", address, amount)
            return None, None, None

    def verify_amount(self, txdata, address, amount):
        """Check that transaction amounts have not somehow changed between confirmations."""

        total = 0

        # This transaction has new confirmations
        for detail in txdata["details"]:

            if detail["category"] != "receive":
                # Don't crash when we are self-sending into back to our wallet
                continue

            if detail["address"] == address:
                # This transaction contained sends to some other addresses too, not just us
                assert detail["amount"] > 0
                total += self.backend.to_internal_amount(detail["amount"])

        return total == amount

    def update_network_transaction_deposit(self, txid, txdata):
        """Create or update NetworkTransaction in the database.

        Updates the confirmation count of inbound network deposit transaction. For all associated receiving addresses and transactions, confirmation and crediting check if performed, account balances updated and ``txupdate`` event fired. Any action is taken only if the confirmation status has changed since the last call.

        :param txid: Network transaction hash

        :param txdata: Transaction details, as given by *bitcoind* backend

        :return: Tuple (new or existing network transaction id, fired txupdate events as a list)
        """

        @self.conflict_resolver.managed_transaction
        def handle_incoming_tx(session):

            txupdate_events = []

            ntx, created = self.coin.coin_description.NetworkTransaction.get_or_create_deposit(session, txid)
            session.flush()

            assert ntx.transaction_type == "deposit"

            # Verify transaction data looks good compared what we have recorded earlier in the database
            if not created:

                if ntx.confirmations == txdata["confirmations"]:
                    # Confirmations have not changed, nothing to do
                    return ntx.id, 0

                for tx in ntx.transactions:
                    assert self.verify_amount(txdata, tx.address.address, tx.amount)

            logger.info("Updating network transaction %d, txid %s, confirmations to %s", ntx.id, ntx.txid, ntx.confirmations)

            ntx.confirmations = txdata["confirmations"]

            # Sum together received per address
            addresses = Counter()  # address -> amount mapping
            for detail in txdata["details"]:
                if detail["category"] == "receive":
                    addresses[detail["address"]] += self.backend.to_internal_amount(detail["amount"])

            # TODO: Filter out address updates which are not managed by our database
            confirmations = txdata["confirmations"]

            for address, amount in addresses.items():
                account_id, transaction_id, credited = self._update_address_deposit(ntx, address, amount, confirmations)

                if not account_id:
                    # This address was not in our system
                    continue

                event_name, event = events.txupdate(network_transaction=ntx.id, txid=txid, transaction=transaction_id, account=account_id, address=address, amount=amount, confirmations=confirmations, credited=True)
                txupdate_events.append(event)

            self.stats["network_transaction_updates"] += 1

            return ntx.id, txupdate_events

        ntx_id, txupdate_events = handle_incoming_tx()

        # Fire event handlers outside the db transaction
        notifier_count = len(self.notifiers.get_all()) if self.notifiers else 0
        logger.info("Posting txupdate notify for %d notifiers", notifier_count)
        if self.notifiers:
            for e in txupdate_events:
                self.notifiers.notify("txupdate", e)

        return ntx_id, txupdate_events

    def handle_wallet_notify(self, txid):
        """Handle incoming wallet notifications.

        Fetch transaction info from the backend and update all receiving addresses we are managing within that transaction.

        :param txid: Network transaction hash
        """
        self.last_wallet_notify = datetime.datetime.utcnow()

        txdata = self.backend.get_transaction(txid)
        return self.update_network_transaction_deposit(txid, txdata)

    def rescan_address(self, address, confirmations):
        """
        :param address: Address object
        """

        raise NotImplementedError()

        balance = self.backend.to_internal_amount(self.backend.listreceivedbyaddress(address.address, confirmations, False))
        if balance != address.balance:
            # Uh oh, our internal bookkeeping is not up-to-date with address,
            # need full rescan
            pass

    def rescan_all(self):
        """Rescan all transactions in a wallet to see if we have miss any.

        TODO: Currently this does not correctly subtract outgoing transactions

        :return: int, number of total transactions found for the wallet
        """

        found = 0
        batch_size = 100
        current = 0

        txs = self.backend.list_transactions(current, batch_size)

        while txs:

            logger.info("Rescanning transactions from %d to %d", current, current + batch_size)

            for tx in txs:
                # TODO See if we can optimize this pulling all tx data from listransactions information without need to do one extra JSON-RPC per tx
                self.handle_wallet_notify(tx["txid"])
                self.count += 1
                found += 1

            current += batch_size
            txs = self.backend.list_transactions(current, batch_size)

        return found
