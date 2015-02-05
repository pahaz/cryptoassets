"""Network transactions are considered open as long as the confirmation threshold has not been reached.

Because backends do not actively report the progress of confirmation status, we poll the backend for all network transactions (deposits, broadcasts) until the confirmation threshold has been reached. For example, *bitcoind* gives you a walletnotify only for 0 and 1 confirmations. *block.io* does not have any confirmation hooks, but you can subcribe to *chain.so* real-time API to receive 0 confirmations notificatoin to an address.

:py:func:`cryptoassets.core.tools.confirmationupdate.update_confirmations` polls the backend. It will scan all transactions where confirmation threshold has not been reached and then ask the backend of more transaction details. Eventually all open incoming transactions exceed the confirmation threshold and we can stop polling them.

The poller is set up in :py:class:`cryptoassets.core.service.main.Service`.

More information about walletnotify behavior

* http://bitcoin.stackexchange.com/a/24483/5464
"""

import logging

from cryptoassets.core.models import GenericConfirmationTransaction


logger = logging.getLogger(__name__)


def get_open_network_transactions(session, NetworkTransaction, confirmation_threshold):
    """Get list of transaction_type, txid of transactions we need to check."""
    ntxs = session.query(NetworkTransaction).filter(NetworkTransaction.confirmations < confirmation_threshold, NetworkTransaction.txid != None)  # noqa
    return [(ntx.transaction_type, ntx.txid) for ntx in ntxs]


def update_confirmations(transaction_updater, confirmation_threshold):
    """Periodically rescan all open transactions for one particular cryptocurrency.

    We try to keep transaction  conflicts in minimum by not batching too many backend operations per each database session.

    :param confirmation_treshold: Rescan the transaction if it has less confirmations than this

    :param transaction_updater: :py:class:`cryptoassets.core.backend.transactionupdater.TransactionUpdater` instance

    :return: Number of txupdate events fired
    """

    Transaction = transaction_updater.coin.transaction_model
    NetworkTransaction = transaction_updater.coin.network_transaction_model
    backend = transaction_updater.backend
    coin = transaction_updater.coin

    assert issubclass(Transaction, (GenericConfirmationTransaction,))
    assert type(confirmation_threshold) == int

    @transaction_updater.conflict_resolver.managed_transaction
    def get_open_ntxs(session):
        return get_open_network_transactions(session, NetworkTransaction, confirmation_threshold)

    open_ntxs = get_open_ntxs()

    if len(open_ntxs) == 0:
        return 0, 0

    logger.debug("Starting open transaction scan, coin:%s open network transactions: %d", coin.name, len(open_ntxs))

    total_txupdate_events = 0
    for transaction_type, txid in open_ntxs:
        assert txid
        txdata = backend.get_transaction(txid)
        logger.debug("Updating confirmations for %s type %s", txid, transaction_type)
        _, txupdate_events = transaction_updater.update_network_transaction_confirmations(transaction_type, txid, txdata)
        total_txupdate_events += len(txupdate_events)

    return txupdate_events
