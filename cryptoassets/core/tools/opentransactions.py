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

    txdata = {}

    txs = session.query(Transaction).filter(Transaction.confirmations < confirmation_threshold)
    for tx in txs:
        # We need to key by transaction id + address because one transaction can send to several addresses
        txdata[(tx.txid, tx.address.address)] = dict(id=tx.id, txid=tx.txid, address=tx.address, amount=tx.amount, confirmations=tx.confirmations)

    return txdata


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
        return get_open_incoming_txs(session, Transaction, confirmation_threshold)

    tx_ids = get_open_txs()

    if len(tx_ids) == 0:
        return

    logger.info("Starting open transaction scan, coin:%s open transactions: %d", coin.name, len(tx_ids))

    for txid_address, tx_existing_data in tx_ids.items():

        txid, address = txid_address

        txdata = backend.get_incoming_transaction_info(txid)

        logger.debug("Polling updates for txid + address pair %s, confirmations now %d", txid_address, tx_existing_data["confirmations"])

        if txdata["confirmations"] != tx_existing_data["confirmations"]:

            logger.debug("Tx confirmation update details %s", txdata)

            assert txdata["confirmations"] > tx_existing_data["confirmations"], "We cannot go backwards in confirmations. Had {}, got {} confirmations".format(tx_existing_data["confirmations"], txdata["confirmations"])

            # Count how many total bitcoins this transaction contains to this specific address. By the protocol you might have several receive entries for the same address in the same transaction
            total = 0

            # This transaction has new confirmations
            for detail in txdata["details"]:

                if detail["category"] != "receive":
                    # Don't crash when we are self-sending into back to our wallet
                    continue

                if detail["address"] == address:
                    # This transaction contained sends to some other addresses too, not just us
                    assert detail["amount"] > 0
                    total += detail["amount"]

            if total == 0:
                # Txid data from the backend did not contain address we had recorded in the database.
                # "Never should happen" - probably somebody playing tricks with no confirmation transactions
                logger.error("We had recorded that txid %s has transfer to address %s, but backend transaction tells otherwise. Txdata: %s", txid, address, txdata)
                continue

            # XXX: Assume backend converted this for us
            # and amount should never change
            assert total == tx_existing_data["amount"]

            transaction_updater.handle_address_receive(txid, address, total, txdata["confirmations"])

            # We have matched the txid + address part and updated the transaction correctly
            tx_updates += 1

    return tx_updates
