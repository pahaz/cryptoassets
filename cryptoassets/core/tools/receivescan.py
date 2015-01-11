"""Scan all receiving addresses to see if we have missed any incoming transactions.

"""

import threading
import logging

from ..backend.transactionupdater import TransactionUpdater


logger = logging.getLogger(__name__)


def get_all_addresses(session, Address):
    """Get the deposit transactions we are aware off."""
    addresses = session.query(Address).values(Address.address)
    return set([address.address for address in addresses])


def get_all_confirmed_network_transactions(session, NetworkTransaction, confirmation_threshold):
    """Give list of network transactions we know we have reached good confirmation level and thus are not interested to ask them from the backend again.

    Note that same ``txid`` may be reported twice in the list.
    """

    # TODO: optimize
    ntxs = session.query(NetworkTransaction).filter(NetworkTransaction.confirmations >= confirmation_threshold).values("txid")
    return set([ntx.txid for ntx in ntxs])


def is_interesting_transaction(txdata, all_addresses):
    """Check if the transaction contains any sending or receiving"""
    return any([(detail["address"] in all_addresses) for detail in txdata["details"]])


def scan_coin(coin, conflict_resolver, event_handlers, batch_size=100):
    """Go through for all received transactions reported by a backend and see if our database is missing any.

    :param coin: Instance of `cryptoassets.core.coin.registry.Coin`

    :param conflict_resolver: Instance of `cryptoassets.core.utils.conflictresolver.ConflictResolver`

    :param event_handlers: Instance of `cryptoassets.core.notify.registry.NotifierRegistry`

    :param batch_size: How many transaction we list from the backend at a time.
    """

    @conflict_resolver.managed_transaction
    def _get_all_addresses(session, addres_model):
        return get_all_addresses(session, addres_model)

    @conflict_resolver.managed_transaction
    def _get_all_confirmed_network_transactions(session, network_transaction_model, confirmation_threshold):
        return get_all_confirmed_network_transactions(session, network_transaction_model, confirmation_threshold)

    start = 0
    batch_size = batch_size
    backend = coin.backend
    found_missed = 0

    transaction_updater = TransactionUpdater(conflict_resolver, coin.backend, coin, event_handlers)

    good_txids = _get_all_confirmed_network_transactions(coin.network_transaction_model, backend.max_tracked_incoming_confirmations)

    all_addresses = _get_all_addresses(coin.address_model)

    def get_batch():
        logger.debug("Scanning incoming transactions %d to %d", start, start+batch_size)
        txs = backend.list_received_transactions(start, batch_size)
        return txs

    txs = get_batch()

    while txs:

        for txid in txs:

            # We know this transaction has plentiful confirmations on our database, we are not interested about it
            if txid in good_txids:
                continue

            txdata = backend.get_transaction(txid)

            # Backend reported this transaction, but it did not concern any of our addresses
            # (Shoud not happen unless you share the backend wallet with other services)
            if not is_interesting_transaction(txdata, all_addresses):
                continue

            # Otherwise let's update this transaction just in case
            transaction_updater.handle_wallet_notify(txid)
            found_missed += 1

        start += batch_size
        txs = get_batch()

    return found_missed


def scan(coins, conflict_resolver, event_handlers):
    """Rescans all coins and wallets.

    :param coins: Instance of :py:class:`cryptoassets.core.coin.registry.CoinRegistry`.

    :param conflict_resolver: Instance of :py:class:`cryptoassets.core.utils.conflictresolver.ConflictResolver`.

    :param event_handlers: Instance of :py:class:`cryptoassets.core.notify.registry.NotifierRegistry`.

    :return: Number of missed txids processed for all coins
    """

    missed = 0
    for name, coin in coins.all():
        missed += scan_coin(coin, conflict_resolver, event_handlers)
    return missed


class BackgroundScanThread(threading.Thread):
    """Helper thread launched on the cryptoassets helper service startup to perform rescan on background."""

    def __init__(self, coins, conflict_resolver, event_handlers):
        self.coins = coins
        self.conflict_resolver = conflict_resolver
        self.event_handlers = event_handlers
        self.running = False
        self.missed_txs = 0
        threading.Thread.__init__(self, daemon=True)

    def run(self):
        self.running = True
        self.missed_txs += scan(self.coins, self.conflict_resolver, self.event_handlers)
