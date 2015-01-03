import datetime
from collections import Counter
import logging

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

    def handle_address_receive(self, txid, address, amount, confirmations):
        """Handle an incoming transaction update to a single address.

        TODO: confirmations is relevant for mined coins only. Abstract it away here.

        We received an update regarding cryptocurrency transaction ``txid``. This may be a new transaction we have not seen before or an existing transaction. If the transaction confirmation count is exceeded, the transaction is also marked as credited and account who this address belongs balance is topped up.

        ``handle_address_receive`` will write the updated data to the database. Relevant event handlers are fired (self.notifiers).

        Note that a single cryptocurrency transaction may contain updates to several addresses or several received sections to a single address.

        :return: tuple (Transaction id, boolean credited) for the Transaction object created/updated related to external txid
        """

        transaction_id = None
        account_id = None
        credited = False

        assert amount > 0

        # Pass confirmations in the extra transaction details
        extra = dict(confirmations=confirmations)

        Address = self.coin.address_model

        @self.conflict_resolver.managed_transaction
        def handle_account_update(session):

            address_obj = session.query(Address).filter(Address.address == address).first()  # noqa

            if address_obj:
                wallet = address_obj.account.wallet

                # Credit the account
                account, transaction = wallet.receive(txid, address, amount, extra)

                confirmations = transaction.confirmations

                logger.info("Wallet notify account %d, address %s, amount %s, tx confirmations %d", account.id, address, amount, confirmations)

                # This will cause Transaction instance to get transaction.id
                session.flush()

                return account.id, transaction.id, (transaction.credited_at is not None)

            else:
                logger.info("Skipping transaction notify for unknown address %s, amount %s", address, amount)
                return None, None, None

        # Write db entry
        account_id, transaction_id, credited = handle_account_update()

        # Tranasactipn is committed in this point, notify the application about the new data in the database
        if transaction_id:
            notifier_count = len(self.notifiers.get_all()) if self.notifiers else 0
            logger.info("Posting txupdate notify for %d notifiers", notifier_count)
            if self.notifiers:
                event_name, data = events.create_txupdate(txid=txid, transaction=transaction_id, account=account_id, address=address, amount=amount, confirmations=confirmations)
                self.notifiers.notify(event_name, data)
            return transaction_id, credited
        else:
            logger.info("No transaction object was created")
            return None, False

    def handle_wallet_notify(self, txid):
        """Handle incoming wallet notifications.

        Fetch transaction info from the backend and update all receiving addresses we are managing within that transaction.

        :param txid: Network transaction hash
        """
        self.last_wallet_notify = datetime.datetime.utcnow()

        txdata = self.backend.get_transaction(txid)

        # ipdb> print(txdata)
        # {'blockhash': '00000000cb7b5d9fed3316cceec1af71b941b77ce0b0588c98a34f05bd292b6f', 'time': 1415201940, 'timereceived': 1416370475, 'details': [{'account': 'test', 'address': 'n23pUFwzyVUXd7t4nZLzkZoidbjNnbQLLr', 'amount': Decimal('1.20000000'), 'category': 'receive'}], 'blockindex': 6, 'walletconflicts': [], 'amount': Decimal('1.20000000'), 'confirmations': 2848, 'txid': 'bfb0ef36cdf4c7ec5f7a33ed2b90f0267f2d91a4c419bcf755cc02d6c0176ebf', 'hex': '01000000017b0fedcafed339974e892f2a6da74e6e35789a60cf6efbf23b9059c346e33f32010000006b483045022100fce7ce10797c4a0bd56d5e64dc0fa1e5d3cdba4b495e2a8d76d9c43e1790d82302207b885373d9fc8dbf08165fd24250174344d6792207d98f051c98280b5a1720510121021f8ab4e791c159ba43a2d45464312f7cbafee6cd6bbcdaafb26b545e1deecf64ffffffff0234634e3e090000001976a9141a257a2ef0e6821f314d074f84a4ece9274d7e9488ac000e2707000000001976a914e138e119752bdd89cf8b46ff283181398d85b55288ac00000000', 'blocktime': 1415201940}

        # Sum together received per address
        addresses = Counter()  # address -> amount mapping
        for detail in txdata["details"]:
            if detail["category"] == "receive":
                addresses[detail["address"]] += self.backend.to_internal_amount(detail["amount"])

        # TODO: Filter out address updates which are not managed by our database

        confirmations = txdata["confirmations"]

        for address, amount in addresses.items():
            self.handle_address_receive(txid, address, amount, confirmations)

        self.count += 1

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
