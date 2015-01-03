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

logger = logging.getLogger(__name__)


def _now():
    return datetime.datetime.utcnow()


class Broadcaster:

    def __init__(self, wallet_model, wallet_id, conflict_resolver):
        self.wallet_model = wallet_model
        self.wallet_id = wallet_id
        self.conflict_resolver = conflict_resolver

    def get_wallet(self, session):
        """Get a wallet instance within db transaction."""
        Wallet = self.wallet_model
        return Wallet.get_by_id(session, self.wallet_id)

    def get_broadcast(self, session, broadcast_id):
        """Get a wallet instance within db transaction."""
        Wallet = self.wallet_model
        Broadcast = Wallet.Broadcast
        return session.query(Broadcast).get(broadcast_id)

    def collect_for_broadcast(self):
        """
        :return: Number of outgoing transactions collected for a broadcast
        """

        @self.conflict_resolver.managed_transaction
        def build_broadcast(session):

            wallet = self.get_wallet(session)

            # Get all outgoing pending transactions which are not yet part of any broadcast
            Transaction = wallet.Transaction
            Broadcast = wallet.Broadcast

            txs = session.query(Transaction).filter(Transaction.state == "pending", Transaction.receiving_account == None, Transaction.broadcast == None)  # noqa

            # TODO: If any priority / mixing rules, they should be applied here
            if txs.count():
                broadcast = Broadcast()
                session.add(broadcast)
                session.flush()
                txs.update(broadcast=broadcast)

            return txs.count()

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
        """

        @self.conflict_resolver.managed_transaction
        def get_ready_broadcasts(session):
            wallet = self.get_wallet(session)
            Broadcast = wallet.Broadcast
            session.query(Broadcast).filter(Broadcast.opened_at == None, Broadcast.closed_at == None)  # noqa

        @self.conflict_resolver.transaction
        def mark_for_sending(session, broadcast_id):
            # Mark we are going to send this broadcast and get backend data needed for to build the network transaction
            b = self.get_broadcast(broadcast_id)
            assert b.opened_at is None
            b.opened_at = _now()
            session.add(b)

        @self.conflict_resolver.transaction
        def mark_sending_done(session, broadcast_id, txid):
            b = self.get_broadcast(broadcast_id)
            assert b.closed_at is None
            b.txid = txid
            b.closed_at = _now()
            session.add(b)

            txs = b.transactions
            txs.update(dict(state="broadcasted", processed_at=_now()))

        @self.conflict_resolver.managed_transaction
        def charge_fees(session, broadcast_id):
            wallet = self.get_wallet(session)
            broadcast = self.get_broadcast(broadcast_id)
            txid = broadcast.txid
            txs = b.transactions
            wallet.charge_network_fees(txs, txid, fee)

        ready_broadcasts = get_ready_broadcasts()

        for b in ready_broadcasts:
            # Note: This is something we must NOT attempt to retry
            logger.info("Opening broadcast %d for sending", b.id)
            outgoing = mark_for_sending(b)

            try:
                txid, fee = self.backend.send(outgoing, "Outgoing broadcast {}".format(b.id))
                assert txid
            except Exception as e:
                # Transaction broadcast died and we don't know why. We are pretty much dead in this situation, as we don't know if it is safe to try to re-broadcast the transaction or not.
                logger.error("Failed to broadcast external transaction %s", e)
                logger.exception(e)

                #: TODO: Throw emergency event here?
                continue

            logger.info("Closing broadcast %d as done", b.id)
            mark_sending_done(b, txid)

            if fee:
                charge_fees(b, fee)

    def do_broadcasts(self):
        self.collect_for_broadcast()
        self.send_broadcasts()
