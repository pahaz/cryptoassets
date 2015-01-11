import unittest
import threading
import time
import os
import pytest

from cryptoassets.core.utils.conflictresolver import ConflictResolver
from cryptoassets.core.utils.conflictresolver import CannotResolveDatabaseConflict

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm import scoped_session
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column
from sqlalchemy import Numeric
from sqlalchemy import Integer

from . import testwarnings

try:
    import psycopg2  # noqa
    HAS_POSTGRESQL = True
except:
    HAS_POSTGRESQL = False


Base = declarative_base()


class TestModel(Base):
    """A sample SQLAlchemy model to demostrate db conflicts. """

    __tablename__ = "test_model"

    #: Running counter used in foreign key references
    id = Column(Integer, primary_key=True)

    #: The total balance of this wallet in the minimum unit of cryptocurrency
    #: NOTE: accuracy checked for Bitcoin only
    balance = Column(Numeric(21, 8))


class ConflictThread(threading.Thread):
    """Launch two of these and they should cause database conflict."""

    def __init__(self, session_factory):
        self.session_factory = session_factory
        self.failure = None
        threading.Thread.__init__(self)

    def run(self):

        session = self.session_factory()
        try:

            # Both threads modify the same wallet simultaneously
            w = session.query(TestModel).get(1)
            w.balance += 1

            # Let the other session to start its own transaction
            time.sleep(1)

            session.commit()
        except Exception as e:
            self.failure = e
            session.rollback()


class ConflictResolverThread(threading.Thread):
    """Launch two of these and they should cause database conflict and then conflictresolver resolves it."""

    def __init__(self, session_factory):
        self.session_factory = session_factory
        self.failure = None
        threading.Thread.__init__(self)
        self.conflict_resolver = ConflictResolver(self.session_factory, retries=1)

    def run(self):

        # Execute the conflict sensitive code inside a managed transaction
        @self.conflict_resolver.managed_transaction
        def myfunc(session):

            # Both threads modify the same wallet simultaneously
            w = session.query(TestModel).get(1)
            w.balance += 1

            # Let the other session to start its own transaction
            time.sleep(1)

            session.commit()

        try:
            myfunc()
        except Exception as e:
            self.failure = e


@pytest.mark.skipif(not HAS_POSTGRESQL, reason="Running this test requires psycopg2 driver + PostgreSQL database unittest-conflict-resolution")
class PostgreSQLConflictResolverTestCase(unittest.TestCase):
    """Check that we execute and retry transactions correctly on Serialiable SQL transaction isolation level.


    """

    def open_session(self):
        return self.Session()

    def setUp(self):

        testwarnings.begone()

        # createdb unittest-conflict-resolution on homebrew based installations
        if "CI" in os.environ:
            self.engine = create_engine('postgresql://postgres@localhost/unittest-conflict-resolution',  isolation_level='SERIALIZABLE')
        else:
            self.engine = create_engine('postgresql:///unittest-conflict-resolution',  isolation_level='SERIALIZABLE')

        # Create a threadh-local automatic session factory
        self.Session = scoped_session(sessionmaker(autocommit=False, autoflush=False, bind=self.engine))

        session = self.open_session()

        # Load Bitcoin models to play around with
        Base.metadata.create_all(self.engine, tables=[TestModel.__table__])

        # Create an wallet with balance of 10
        w = session.query(TestModel).get(1)
        if not w:
            w = TestModel()
            session.add(w)

        w.balance = 10

        session.commit()

    def test_conflict(self):
        """Run database to a transaction conflict and see what exception it spits out, and make sure we know this is the exception we expect."""

        def session_factory():
            return self.open_session()

        t1 = ConflictThread(session_factory)
        t2 = ConflictThread(session_factory)

        t1.start()
        t2.start()

        t1.join()
        t2.join()

        # Either thread spits out:
        # sqlalchemy.exc.OperationalError: (TransactionRollbackError) could not serialize access due to concurrent update
        #  'UPDATE btc_wallet SET updated_at=%(updated_at)s, balance=%(balance)s WHERE btc_wallet.id = %(btc_wallet_id)s' {'btc_wallet_id': 1, 'balance': Decimal('11.00000000'), 'updated_at': datetime.datetime(2014, 12, 18, 1, 53, 58, 583219)}
        failure = t1.failure or t2.failure or None
        self.assertIsNotNone(failure)
        self.assertTrue(ConflictResolver.is_retryable_exception(failure), "Got exception {}".format(failure))

    def test_conflict_resolved(self):
        """Use conflict resolver to resolve conflict between two transactions and see code retry is correctly run."""

        def session_factory():
            return self.open_session()

        t1 = ConflictResolverThread(session_factory)
        t2 = ConflictResolverThread(session_factory)

        t1.start()
        t2.start()

        t1.join()
        t2.join()

        # sqlalchemy.exc.OperationalError: (TransactionRollbackError) could not serialize access due to concurrent update
        #  'UPDATE btc_wallet SET updated_at=%(updated_at)s, balance=%(balance)s WHERE btc_wallet.id = %(btc_wallet_id)s' {'btc_wallet_id': 1, 'balance': Decimal('11.00000000'), 'updated_at': datetime.datetime(2014, 12, 18, 1, 53, 58, 583219)}
        failure = t1.failure or t2.failure or None
        self.assertIsNone(failure)

        session = session_factory()
        w = session.query(TestModel).get(1)
        self.assertEqual(w.balance, 12)  # two increments
        session.close()

        success = sum([t1.conflict_resolver.stats["success"], t2.conflict_resolver.stats["success"]])
        retries = sum([t1.conflict_resolver.stats["retries"], t2.conflict_resolver.stats["retries"]])
        errors = sum([t1.conflict_resolver.stats["errors"], t2.conflict_resolver.stats["errors"]])

        self.assertEqual(success, 2)
        self.assertEqual(retries, 1)
        self.assertEqual(errors, 0)

    def test_conflict_some_other_exception(self):
        """See that unknown exceptions are correctly reraised by managed_transaction."""

        def session_factory():
            return self.open_session()

        c = ConflictResolver(session_factory, 1)

        @c.managed_transaction
        def do_stuff(session):
            raise ValueError("Unknown exception")

        self.assertRaises(ValueError, do_stuff)
        self.assertEqual(c.stats["errors"], 1)

    def test_give_up(self):
        """See that the conflict resolver gives up after using given number of attempts to replay transactions."""

        def session_factory():
            return self.open_session()

        # The resolved has retry count of 1,
        # First t1 success, t2 and t3 clases
        # Then t2 success, t3 retries but is out of
        t1 = ConflictResolverThread(session_factory)
        t2 = ConflictResolverThread(session_factory)
        t3 = ConflictResolverThread(session_factory)

        t1.start()
        t2.start()
        t3.start()

        t1.join()
        t2.join()
        t3.join()

        failure = t1.failure or t2.failure or t3.failure or None
        self.assertIsInstance(failure, CannotResolveDatabaseConflict)

        unresolved = sum([t1.conflict_resolver.stats["unresolved"], t2.conflict_resolver.stats["unresolved"], t3.conflict_resolver.stats["unresolved"]])
        self.assertEqual(unresolved, 1)

