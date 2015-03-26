import datetime
from collections import Counter
import logging
from decimal import Decimal

from sqlalchemy.orm.session import Session

from ..coin.registry import Coin
from ..event.registry import EventHandlerRegistry
from ..event import events

from ..utils.conflictresolver import ConflictResolver


logger = logging.getLogger(__name__)


#: bitcoind gettransaction details and our network transaction types
_detail_categories = {
    "deposit": "receive",
    "broadcast": "send"
}


class TransactionUpdater:
    """TransactionUpdater write transactions updates from API/backend to the database.

    TransactionUpdater uses :py:class:`cryptoassets.core.utils.conflictresolver.ConflictResolver` database transaction helper when updating transactions. This gives us guarantees that updates having possible db transaction conflicts are gracefully handled.

    The backend has hooked up some kind of wallet notify handler. The wallet notify handler uses TransactionUpdater to write updates of incoming transactoins to the database.

    TransactionUpdater is also responsible to fire any notification handlers to signal the cryptoassets client application to handle new transactions.

    TransactionUpdater is generally run inside :py:class:`cryptoassets.core.service.main.Server` process, as this process is responsible for all incoming transaction updates. No web or other front end should try to make their own updates.
    """

    def __init__(self, conflict_resolver, backend, coin, event_handler_registry):
        """
        :param conflict_resolver: :py:class:`cryptoassets.core.utils.conflictresolver.ConflictResolver`

        :param backend: :py:class:`cryptoasets.core.backend.base.CoinBackend` instance. TODO: To be removed - redundant with ``coin``.

        :param coin: :py:class:`cryptoasets.core.coin.registry.Coin` instance

        :param event_handler_registry: :py:class`cryptoassets.core.event.registry.EventHandlerRegistry` instance
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

        if event_handler_registry:
            assert isinstance(event_handler_registry, EventHandlerRegistry)
            #: event_handler_registry registry we are going to inform about transaction status updates
            self.event_handler_registry = event_handler_registry
        else:
            self.event_handler_registry = None

        #: Diagnostics and bookkeeping statistics
        self.stats = Counter(network_transaction_updates=0, deposit_updates=0, broadcast_updates=0)

    def _update_address_deposit(self, ntx, address, amount, confirmations):
        """Handle an incoming transaction update to a single address.

        TODO: confirmations is relevant for mined coins only. Abstract it away here.

        We received an update regarding cryptocurrency transaction ``txid``. This may be a new transaction we have not seen before or an existing transaction. If the transaction confirmation count is exceeded, the transaction is also marked as credited and account who this address belongs balance is topped up.

        ``_update_address_deposit`` will write the updated data to the database.

        Note that a single cryptocurrency transaction may contain updates to several addresses or several received sections to a single address.

        :return: tuple (Transaction id, boolean credited) for the Transaction object created/updated related to external txid
        """

        assert amount > 0

        session = Session.object_session(ntx)

        Address = self.coin.address_model

        address_obj = session.query(Address).filter(Address.address == address).first()  # noqa

        if address_obj:

            assert address_obj.account, "Tried to _update_deposit() on non-deposit address. Depositing to: {}, address object is {}, label {}".format(address, address_obj, address_obj.label)

            wallet = address_obj.account.wallet

            # Credit the account
            # Pass confirmations in the extra transaction details
            extra = dict(confirmations=confirmations)

            account, transaction = wallet.deposit(ntx, address, amount, extra)

            confirmations = transaction.confirmations

            logger.info("Wallet notify account %d, address %s, amount %s, tx confirmations %d", account.id, address, amount, confirmations)

            # This will cause Transaction instance to get transaction.id
            session.flush()

            return account.id, transaction.id, (transaction.credited_at is not None)

        else:
            logger.info("Skipping transaction notify for unknown address %s, amount %s", address, amount)
            return None, None, None

    def _is_known_deposit_address(self, session, address):
        """Check if the address is belonging to us or in some third party system in merged transaction."""
        Address = self.coin.address_model
        address_obj = session.query(Address).filter(Address.address == address).first()  # noqa

        # We have not seen this address before
        if not address_obj:
            return False

        # This is not a deposit address generated by us
        if not address_obj.is_deposit():
            return False

        return True

    def _get_broadcasted_transactions(self, ntx):
        """Get and verify the list of transaction broadcast concerned.

        We received an update regarding cryptocurrency transaction ``txid``. Because this is an outgoing transaction we must know about transaction this already.

        Note that a single network transaction may contain several outbound transactions. We will return a list of all outbound transactions which received updates.

        :return: List of Transaction objects that were updatesd
        """

        session = Session.object_session(ntx)

        Transaction = self.coin.transaction_model

        transactions = session.query(Transaction).filter(Transaction.network_transaction == ntx, Transaction.state.in_(["pending", "broadcasted"]))  # noqa

        transactions = list(transactions)

        assert len(transactions) > 0
        return transactions

    def verify_amount(self, transaction_type, txdata, address, amount):
        """Check that transaction amounts have not somehow changed between confirmations.

        It gets tricky here because bitcoind reports its internal stuff and has negative amounts for send transactions, versus what you see in blockchain and other services is only receiving outputs. We place some temporary workaround we hope to get rid of later.
        """

        total = 0

        # set by block.io to make sure we don't do bitcoind mappings
        if txdata.get("only_receive"):
            transaction_type = "deposit"

        # This transaction has new confirmations
        for detail in txdata["details"]:

            if detail["category"] != _detail_categories[transaction_type]:
                # Don't crash when we are self-sending into back to our wallet.
                # This will filter out "send" and "receive" both inside the same tx
                continue

            assert isinstance(detail["amount"], Decimal), "Problem decoding txdata detail {}".format(detail)

            if detail["address"] == address:
                # This transaction contained sends to some other addresses too, not just us
                if transaction_type == "deposit":
                    assert detail["amount"] > 0
                    total += self.backend.to_internal_amount(detail["amount"])
                else:
                    assert detail["amount"] < 0
                    total += -self.backend.to_internal_amount(detail["amount"])

        if total != amount:
            logger.warning("verify_amount() failed. Expected: %s got: %s", amount, total)

        return total == amount

    def update_network_transaction_confirmations(self, transaction_type, txid, txdata):
        """Create or update NetworkTransaction in the database.

        Ask the backend about updates for a network transaction. Any action is taken only if the confirmation count has changed since the last call.

        For desposits, updates the confirmation count of inbound network deposit transaction. For all associated receiving addresses and transactions, confirmation and crediting check if performed, account balances updated and ``txupdate`` event fired.

        For broadcasts, updates the confirmation count of outbound transactions.

        Relevant event handlers are fired (:py:attr:`cryptoassets.core.transactionupdater.TransactionUpdater.event_handler_registry`)

        :param transaction_type: "deposit" or "broadcast". Note that we might have two ntx's for one real network transaction, as we are sending bitcoins to ourselves.

        :param txid: Network transaction hash

        :param txdata: Transaction details, as given by the backend, translated to *bitcoind* format

        :return: Tuple (new or existing network transaction id, fired txupdate events as a list)
        """

        assert txid
        assert txdata

        @self.conflict_resolver.managed_transaction
        def handle_ntx_update(session, transaction_type, txid, txdata):

            txupdate_events = []

            NetworkTransaction = self.coin.coin_description.NetworkTransaction

            if transaction_type == "deposit":
                # In the case of deposit, we may need to create initial ntx event_handler_registry
                ntx, created = NetworkTransaction.get_or_create_deposit(session, txid)
                session.flush()
            elif transaction_type == "broadcast":
                # For broadcasts, we should always know about ntx beforehand as broadcasted it
                ntx = session.query(NetworkTransaction).filter_by(transaction_type="broadcast", txid=txid).first()
                assert ntx, "Tried to update non-existing broadcast {}".format(txid)
                created = False
            else:
                raise AssertionError("Unknown network transaction type {}".format(transaction_type))

            assert ntx.txid == txid, "Corrupted txid in the look-up process"

            # Make sure we don't think we are updating deposit, when in fact, we are updating broadcast
            assert transaction_type == ntx.transaction_type, "Got confused with network transaction {}, asserted it is {}".format(ntx, transaction_type)

            # Confirmations have not changed, nothing to do
            if not created:
                if ntx.confirmations == txdata["confirmations"]:
                    return ntx.id, []

            confirmations = ntx.confirmations = txdata["confirmations"]
            self.stats["network_transaction_updates"] += 1

            logger.info("Updating network transaction %d, type %s, state %s, txid %s, confirmations to %s", ntx.id, ntx.transaction_type, ntx.state, ntx.txid, ntx.confirmations)

            if ntx.transaction_type == "deposit":

                # Verify transaction data looks good compared what we have recorded earlier in the database
                for tx in ntx.transactions:

                    # XXX: verify_amount() fails with multisig transactions?
                    # https://chain.so/tx/BTC/40ad00b473f2cc9f33a84779eb22b8d233ef47b35a2afec77e2fff805af60084
                    if not self.verify_amount(ntx.transaction_type, txdata, tx.address.address, tx.amount):
                        logger.warn("The total amount of txid %s, type %s, for address %s did not match. Expected: %s. Txdata: %s", txid, ntx.transaction_type, tx.address.address, tx.amount, txdata)

                # Sum together received per address
                addresses = Counter()  # address -> amount mapping

                # XXX: room for optimization, do _is_known_deposit in single SQL batch
                for detail in txdata["details"]:
                    if detail["category"] == "receive":

                        # Do not care about the address unless it is our receiving address, otherwise it can be just some third party transfer in a merged transaction
                        if not self._is_known_deposit_address(session, detail["address"]):
                            logger.debug("Bailing out unknown address %s", detail["address"])
                            continue

                        addresses[detail["address"]] += self.backend.to_internal_amount(detail["amount"])

                for address, amount in addresses.items():

                    # Handle updates to deposits
                    account_id, transaction_id, credited = self._update_address_deposit(ntx, address, amount, confirmations)

                    logger.debug("Received deposit update for account %s, address %s, credited %s, confirmations %d", account_id, address, credited, confirmations)

                    if not account_id:
                        # This address was not in our system
                        continue

                    self.stats["deposit_updates"] += 1

                    event = events.txupdate(coin_name=self.coin.name, network_transaction=ntx.id, transaction_type=ntx.transaction_type, txid=txid, transaction=transaction_id, account=account_id, address=address, amount=amount, confirmations=confirmations, credited=True)
                    txupdate_events.append(event)

            else:
                # Handle updates to broadcasts
                transactions = self._get_broadcasted_transactions(ntx)

                assert len(transactions) > 0

                # TODO: Reverify outgoing amounts here

                for t in transactions:

                    logger.debug("Received broadcast update for transaction %d", t.id)

                    event = events.txupdate(coin_name=self.coin.name, network_transaction=ntx.id, transaction_type=ntx.transaction_type, txid=txid, transaction=t.id, account=t.sending_account.id, address=t.address.address, amount=t.amount, confirmations=confirmations, credited=None)
                    txupdate_events.append(event)

                    self.stats["broadcast_updates"] += 1

            return ntx.id, txupdate_events

        ntx_id, txupdate_events = handle_ntx_update(transaction_type, txid, txdata)

        if txupdate_events:

            # Fire event handlers outside the db transaction
            notifier_count = len(self.event_handler_registry.get_all()) if self.event_handler_registry else 0
            logger.info("Posting txupdate notify for %d event_handler_registry, current transaction updater stats %s", notifier_count, self.stats)
            if self.event_handler_registry:
                for e in txupdate_events:
                    self.event_handler_registry.trigger("txupdate", e)

        return ntx_id, txupdate_events

    def handle_wallet_notify(self, txid):
        """Handle incoming wallet notifications.

        Fetch transaction info from the backend and update all receiving addresses we are managing within that transaction.

        :param txid: Network transaction hash
        """
        self.last_wallet_notify = datetime.datetime.utcnow()

        txdata = self.backend.get_transaction(txid)
        # XXX: bitcoind sends updates for broacasted transactions too? In any case this will filter them out and confirmations are updated via tools.confirmationupdate
        return self.update_network_transaction_confirmations("deposit", txid, txdata)
