import os
import unittest
import transaction
import threading
import sys
import time

import pytest

from cryptoassets.core.models import DBSession
from cryptoassets.core.models import Base
from cryptoassets.core.coin.bitcoin.models import BitcoinAccount
from cryptoassets.core.coin.bitcoin.models import BitcoinAddress
from cryptoassets.core.coin.bitcoin.models import BitcoinTransaction
from cryptoassets.core.coin.bitcoin.models import BitcoinWallet
from cryptoassets.core.utils.conflictresolver import ConflictResolver

from sqlalchemy import create_engine
from sqlalchemy import pool
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm import scoped_session

from . import warnhide

try:
    import psycopg2  # noqa
    from psycopg2.extensions import TransactionRollbackError
    HAS_POSTGRESQL = True
except:
    HAS_POSTGRESQL = False


class ConflictThread(threading.Thread):
    """Launch two of these and they should cause database conflict."""
    def __init__(self, session_factory):
        self.session_factory = session_factory
        self.failure = None
        threading.Thread.__init__(self)

    def run(self):

        try:
            session = self.session_factory()

            # Both threads modify the same wallet simultaneously
            w = session.query(BitcoinWallet).get(1)
            w.balance += 1

            # Let the other session to start its own transaction
            time.sleep(1)

            session.commit()
        except Exception as e:
            self.failure = e


@pytest.mark.skipif(HAS_POSTGRESQL == False, reason="Running this test requires psycopg2 driver + PostgreSQL database unittest-conflict-resolution")
class PostgrSQLConflictResolverTestCase(unittest.TestCase):
    """Check that we execute and retry transactions correctly on Serialiable SQL transaction isolation level.


    """

    def create_session(self, engine):
        # createdb unittest-conflict-resolution on homebrew based installations
        Session = sessionmaker()
        Session.configure(bind=engine)
        return Session()

    def setUp(self):
        """
        """

        warnhide.begone()

        self.engine = create_engine('postgresql:///unittest-conflict-resolution',  isolation_level='SERIALIZABLE')
        self.session = self.create_session(self.engine)
        # Load Bitcoin models to play around with
        Base.metadata.create_all(self.engine, tables=[BitcoinAccount.__table__, BitcoinAddress.__table__, BitcoinTransaction.__table__, BitcoinWallet.__table__])
        self.session.commit()

    def test_conflict(self):
        """Run database to a transaction conflict and see what it spits out."""

        w = BitcoinWallet()
        w.balance = 10
        self.session.add(w)
        self.session.commit()

        def session_factory():
            return self.create_session(self.engine)

        t1 = ConflictThread(session_factory)
        t2 = ConflictThread(session_factory)

        t1.start()
        t2.start()

        t1.join()
        t2.join()

        # sqlalchemy.exc.OperationalError: (TransactionRollbackError) could not serialize access due to concurrent update
        #  'UPDATE btc_wallet SET updated_at=%(updated_at)s, balance=%(balance)s WHERE btc_wallet.id = %(btc_wallet_id)s' {'btc_wallet_id': 1, 'balance': Decimal('11.00000000'), 'updated_at': datetime.datetime(2014, 12, 18, 1, 53, 58, 583219)}
        failure = t1.failure or t2.failure or None
        self.assertIsNotNone(failure)
        self.assertTrue(ConflictResolver.is_retryable_exception(failure))



