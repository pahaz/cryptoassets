"""Transactions are considered open as long as the confirmation threshold has not been reached. Because backends do not actively report the progress of confirmation status, we poll the backend for all transactions under confirmation threshold until the treshold has been reached. For example, *bitcoind* gives you a walletnotify only for 0 and 1 confirmations.

:py:func:`cryptoassets.core.tools.opentransactions.rescan` polls the backend. It will scan all transactions where confirmation threshold has not been reached and then ask the backend of more transaction details. Eventually all open incoming transactions exceed the confirmation threshold and we can stop polling them.

The poller is set up in :py:class:`cryptoassets.core.service.main.Service`.

More information about walletnotify behavior

* http://bitcoin.stackexchange.com/a/24483/5464
"""

import logging

from cryptoassets.core.models import GenericConfirmationTransaction


logger = logging.getLogger(__name__)


def get_open_incoming_txs(session, Transaction, confirmation_threshold):
    """Get list of ids of transactions we need to check."""
    txs = session.query(Transaction).filter(Transaction.confirmations < confirmation_threshold)
    for tx in txs:
        yield tx.id, tx.txid, tx.confirmations


def rescan(transaction_updater, confirmation_threshold):
    """Periodically rescan all open transactions for one particular cryptocurrency.

    :param confirmation_treshold: Rescan the transaction if it has less confirmations than this

    :param transaction_updater: :py:class:`cryptoassets.core.backend.transactionupdater.TransactionUpdater` instance

    :return: Number of confirmation updates performed
    """

    Transaction = transaction_updater.coin.transaction_model
    backend = transaction_updater.backend
    coin = transaction_updater.coin

    assert issubclass(Transaction, (GenericConfirmationTransaction,))
    assert type(confirmation_threshold) == int

    tx_updates = 0

    @transaction_updater.conflict_resolver.managed_transaction
    def get_open_txs(session):
        return list(get_open_incoming_txs(session, Transaction, confirmation_threshold))

    tx_ids = get_open_txs()

    if len(tx_ids) == 0:
        return

    logger.info("Starting open transaction scan, coin:%s open transactions: %d", coin.name, len(tx_ids))

    for id, txid, confirmations in tx_ids:
        logger.debug("Polling updates for txid %s", txid)
        txdata = backend.get_incoming_transaction_info(txid)

        if txdata["confirmations"] != confirmations:
            tx_updates += 1

            logger.debug("Tx confirmation update details %s", txdata)

            assert txdata["confirmations"] > confirmations, "We cannot go backwards in confirmations. Had {}, got {} confirmations".format(confirmations, txdata["confirmations"])

            # This transaction has new confirmations
            for detail in txdata["details"]:

                if detail["category"] != "receive":
                    # Don't crash when we are self-sending into back to our wallet
                    continue

                # XXX: Assume backend converted this for us
                amount = detail["amount"]
                address = detail["address"]
                transaction_updater.handle_address_receive(txid, address, amount, confirmations)

    return tx_updates
