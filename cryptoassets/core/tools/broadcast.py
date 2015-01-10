"""Broadcast outgoing transactions.

Broadcaster is responsible for the following things

* Check that there hasn't been any interrupted broadcats before

* Make sure there can be one and only one attempt to broadcast at any moment - so we don't have double broadcast problems

* Scan database for outgoing external transactions

* Merge and allocate these transactions to outgoing broadcasts

* If there are any unbroadcasted broadcasts, mark them scheduled for broadcast and attempt to broadcast them
"""

import datetime
import logging
from collections import Counter

logger = logging.getLogger(__name__)


def _now():
    return datetime.datetime.utcnow()


class Broadcaster:
    """Create and send transactions to the cryptoasset networks."""

    def __init__(self, wallet, conflict_resolver, backend):

        assert wallet.id, "We can operate only on persisted wallets"

        self.wallet_model = wallet.__class__
        self.wallet_id = wallet.id
        self.conflict_resolver = conflict_resolver
        self.backend = backend

    def get_wallet(self, session):
        """Get a wallet instance within db transaction."""
        Wallet = self.wallet_model
        return Wallet.get_by_id(session, self.wallet_id)

    def get_broadcast(self, session, broadcast_id):
        """Get a wallet instance within db transaction."""

        assert type(broadcast_id) == int

        NetworkTransaction = self.wallet_model.coin_description.NetworkTransaction
        ntx = session.query(NetworkTransaction).get(broadcast_id)
        assert ntx.transaction_type == "broadcast"
        return ntx

    def collect_for_broadcast(self):
        """
        :return: Number of outgoing transactions collected for a broadcast
        """

        @self.conflict_resolver.managed_transaction
        def build_broadcast(session):

            wallet = self.get_wallet(session)

            # Get all outgoing pending transactions which are not yet part of any broadcast
            NetworkTransaction = wallet.coin_description.NetworkTransaction

            txs = wallet.get_pending_outgoing_transactions()

            # TODO: If any priority / mixing rules, they should be applied here
            if txs.count() > 0:
                count = txs.count()
                broadcast = NetworkTransaction()
                broadcast.transaction_type = "broadcast"
                broadcast.state = "pending"
                broadcast.opened_at = None
                broadcast.closed_at = None
                session.add(broadcast)
                session.flush()
                txs.update({"network_transaction_id": broadcast.id})

                logger.info("Collected %d outgoing transaction for broadcast %d", count, broadcast.id)
            else:
                logger.debug("Did not find outgoing transactions for broadcast")
                count = 0

            return count

        return build_broadcast()

    def check_interrupted_broadcasts(self):
        """Check that there aren't any broadcasts which where opened, but never closed.

        :return: List Open broadcast ids or empty list if all good
        """
        @self.conflict_resolver.managed_transaction
        def get_open_broadcasts(session):
            wallet = self.get_wallet(session)
            Broadcast = wallet.Broadcast
            bs = session.query(Broadcast).filter(Broadcast.opened_at != None, Broadcast.closed_at == None)  # noqa
            return [b.id for b in bs]

        return get_open_broadcasts()

    def send_broadcasts(self):
        """Pick up any unbroadcasted broadcasts and attempt to send them.

        Carefully do broadcasts within managed transactions, so that if something goes wrong we have a clear audit trail where it failed. Then one can manually check the blockchain if our transaction got there and close the broadcast by hand.

        :return: tuple (broadcasted network transaction count, total charged network fees)
        """

        @self.conflict_resolver.managed_transaction
        def get_ready_broadcasts(session):
            wallet = self.get_wallet(session)
            NetworkTransaction = wallet.coin_description.NetworkTransaction
            return session.query(NetworkTransaction).filter(NetworkTransaction.transaction_type == "broadcast", NetworkTransaction.opened_at == None, NetworkTransaction.closed_at == None)  # noqa

        @self.conflict_resolver.managed_non_retryable_transaction
        def mark_for_sending(session, broadcast_id):
            """Mark we are going to send this broadcast and get backend data needed for to build the network transaction.

            :yield: (address, amount) tuples how much to send to each address
            """
            b = self.get_broadcast(session, broadcast_id)
            assert b.opened_at is None
            b.opened_at = _now()
            session.add(b)

            outputs = Counter()

            for tx in b.transactions:
                assert tx.state == "pending"
                assert tx.receiving_account is None
                assert tx.amount > 0
                assert tx.address
                assert tx.address.address
                outputs[tx.address.address] += tx.amount

            return outputs

        @self.conflict_resolver.managed_non_retryable_transaction
        def mark_sending_done(session, broadcast_id, txid):
            b = self.get_broadcast(session, broadcast_id)
            assert b.closed_at is None
            b.txid = txid
            b.closed_at = _now()
            b.state = "broadcasted"
            session.add(b)

            # TODO: See if we can write update() more neatly
            tx_ids = [tx.id for tx in b.transactions]
            Transaction = b.coin_description.Transaction
            session.query(Transaction).filter(Transaction.id.in_(tx_ids)).update(dict(state="broadcasted", processed_at=_now()), synchronize_session=False)

        @self.conflict_resolver.managed_transaction
        def charge_fees(session, broadcast_id, fee):
            wallet = self.get_wallet(session)
            broadcast = self.get_broadcast(session, broadcast_id)
            return wallet.charge_network_fees(broadcast, fee)

        ready_broadcasts = get_ready_broadcasts()
        count = ready_broadcasts.count()
        if count == 0:
            logger.debug("No broadcasts ready for sending to network")
        else:
            logger.info("%d broadcasts prepared for sending", count)

        broadcasted_count = 0
        total_fees = 0

        for b in ready_broadcasts:
            # Note: This is something we must NOT attempt to retry
            logger.info("Opening broadcast %d for sending", b.id)
            outgoing = mark_for_sending(b.id)

            try:
                txid, fee = self.backend.send(outgoing, "Outgoing broadcast {}".format(b.id))
                assert txid
                broadcasted_count += 1
            except Exception as e:
                # Transaction broadcast died and we don't know why. We are pretty much dead in this situation, as we don't know if it is safe to try to re-broadcast the transaction or not.
                logger.error("Failed to broadcast external transaction %s", e)
                logger.exception(e)

                #: TODO: Throw emergency event here?
                continue

            logger.info("Closing broadcast %d as done, it got txid %s", b.id, txid)
            mark_sending_done(b.id, txid)

            if fee:
                charge_fees(b.id, fee)
                total_fees += fee

        return broadcasted_count, total_fees

    def do_broadcasts(self):
        """Collect new outgoing transactions for a broadcast and send out all existing and new outgoing transactions."""
        self.collect_for_broadcast()
        return self.send_broadcasts()
