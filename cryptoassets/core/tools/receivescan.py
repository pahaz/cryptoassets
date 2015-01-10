"""Scan all receiving addresses to see if we have missed any incoming transactions.

"""

import threading

from ..backend.transactionupdater import TransactionUpdater


def get_all_receiving_addresses(session, Address):
    """Collect addresses we need to rescn."""

    out = []
    addresses = session.query(Address).filter(Address.account != None)  # noqa
    for addr in addresses:
        out.append(addr.address)

    return out


def get_missed_txids(session, address_model, address, txids_in_address):
    """Check if our database is missing any received transaction

    :param txids: List of txids arried to this address

    :return: set of transaction txids we don't have accounting for this addres
    """
    Address = address_model

    address_obj = session.query(Address).filter(Address.address == address, Address.account != None).first()  # noqa

    if not address_obj:
        # Cannot update received txs for addresses we are not tracking in our database.
        # Should not happen unless backend is shared between wallets.
        return

    address_txids = [t.txids for t in address.transactions]

    missed_txids = set()

    for txid in txids_in_address:
        if txid not in address_txids:
            missed_txids.append(txid)

    return missed_txids


def scan_coin(coin, conflict_resolver, event_handlers):

    @conflict_resolver.managed_transaction
    def _get_all_receiving_addresses(session, address_model):
        return get_all_receiving_addresses(session, address_model)

    @conflict_resolver.managed_transaction
    def _get_missed_txids(session, address_model, address, txids_in_address):
        return get_all_receiving_addresses(session, address_model, address, txids_in_address)

    transaction_updater = TransactionUpdater(conflict_resolver, coin.backend, coin, event_handlers)

    # Perform one db transaction per backend API call
    missed_txids = set()
    for address in _get_all_receiving_addresses(coin.address_model):
        backend = coin.backend
        # Get all tranactions for this particular address
        received_txids = backend.list_received_by_address(address, dict(confirmations=0))
        missed_txids |= _get_missed_txids(coin.address_model, address, received_txids)

    # Perform one db transaction per backend API call
    for txid in missed_txids:
        transaction_updater.handle_wallet_notify(txid)

    return len(missed_txids)


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
