"""ConflictResolver is a helper class to provide serialized transaction conflict resolution mechanism in your SQLAlchemy application.

Preface
--------

Transaction conflict resolution is a way to deal with concurrency and `race condition <http://en.wikipedia.org/wiki/Race_condition>`_ issues within multiuser application. It is a way to resolve race conditions when two users, or two threads, are performing an action affecting the same data set simultaneously.

There are two basic ways of `concurrency control <http://en.wikipedia.org/wiki/Concurrency_control>`_

* `Up-front locking <http://en.wikipedia.org/wiki/Lock_%28computer_science%29>`_: You use interprocess / interserver locks to signal you are about to access and modify resources. If there are concurrent access the actors accessing the resource wait for the lock before taking action. This is `pessimistic concurrency control mechanism <http://en.wikipedia.org/wiki/Concurrency_control#Concurrency_control_mechanisms>`_.

* `Transaction serialization <http://en.wikipedia.org/wiki/Serializability>`_: Database detects concurrent access from different clients (a.k.a serialization anomaly) and do not let concurrent modifications to take place. Instead, only one transaction is let through and other conflicting transactions are rolled back. The strongest level of `transaction isolation <http://en.wikipedia.org/wiki/Isolation_%28database_systems%29>`_ is achieved using SQL `Serializable <http://en.wikipedia.org/wiki/Isolation_%28database_systems%29#Serializable>`_ isolation level. This is `optimistic concurrency control mechanism <http://en.wikipedia.org/wiki/Concurrency_control#Concurrency_control_mechanisms>`_.

For complex systems, locking may pose scalability and complexity issues. More fine grained locking is required, placing cognitive load on the software developer to carefully think and manage all locks upfront to prevent race conditions and deadlocks. Thus, `locking may be error prone approach in real world application development <http://en.wikipedia.org/wiki/Software_transactional_memory#Conceptual_advantages_and_disadvantages>`_ (TBD needs better sources).

Relying on database transaction serialization is easier from the development perspective. If you use serialized transactions you know there will never be database race conditions. In the worst case there is an user error saying there was concurrency error. But transaction serialization creates another problem: your application must be aware of potential transaction conflicts and in the case of transaction conflict it must be able to recover from them.

Please note that when system is under high load and having high concurrent issue rate, both approaches will lead to degraded performance. In pessimistic approach, clients are waiting for locks, never getting them and eventually timing out. In optimistic approach high transaction conflict rate may exceed the rate the system can successfully replay transactions. Long running transaction are also an issue in both approaches, thus batch processing is encouraged to use limited batch size for each transaction if possible.

Benefits and design goals
---------------------------

:py:class:`cryptoassets.core.utils.conflictresolver.ConflictResolver` is a helper class to manage serialized transaction conflicts in your code and resolve them in idiomatic Python manner. The design goals include

* Race condition free codebase because there is no need for application level locking

* Easy, Pythonic, to use

* Simple

* Have fine-grained control over transaction life cycle

* Works with `SQLAlchemy <http://sqlalchemy.org/>`_

These all should contribute toward cleaner, more robust and bug free, application codebase.

The work was inspired by `ZODB transaction package <https://pypi.python.org/pypi/transaction>`_ which provides abstract two-phase commit protocol for Python. *transaction* package contains more features, works across databases, but also has more complex codebase and lacks decorator approach provided by *ConflictResolver*. Whereas ConflictResolver works directly with SQLAlchemy sessions, making it more straightforward to use in SQLAlchemy-only applications.

Transaction retries
-----------------------

In the core of transaction serialization approach is recovery from the transaction conflict. If you do not have any recovery mechanism, when two users edit the same item on a website and press save simultaneously, leading to a transaction conflict in the database, one of the user gets save succeed the other gets an internal error page. The core principle here is that we consider transaction conflict a rare event under normal system load conditions i.e. it is rare users press the save simultaneously. But it still very bad user experience to serve an error page for  one of the users, especially if the system itself knows how it could recovery from the situation - without needing intervention from the user.

*ConflictResolver* approach to recovery is to

* Run a transaction sensitive code within a marked Python code block

* If the code block raises an exception which we identify to be a transaction conflict error from the database, just reset the situation and replay the code block

* Repeat this X times and give up if it seems like our transaction is never going through (because of too high system load or misdesigned long running transaction blocking all writes)

Marked Python code blocks are created using Python `function decorators <https://www.python.org/dev/peps/pep-0318/>`_. This is not optimal approach in the sense of code cleanness and Python ``with`` block would be preferred. However, Python ``with`` `lacks ability to run loops which is prerequisite for transaction retries <http://stackoverflow.com/q/27351433/315168>`_. However combined with Python `closures <http://stackoverflow.com/q/4020419/315168>`_, the boilerplate is quite minimal.

Example
---------

Here is a simple example how to use ConflictResolver::

    from cryptoassets.core.utils.conflictresolver import ConflictResolver
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    engine = create_engine('postgresql:///unittest-conflict-resolution',
        isolation_level='SERIALIZABLE')

    # Create new session for SQLAlchemy engine
    def create_session():
        Session = sessionmaker()
        Session.configure(bind=engine)
        return Session()

    conflict_resolver = ConflictResolver(create_session, retries=3)

    # Create a decorated function which can try to re-run itself in the case of conflict
    @conflict_resolver.managed_transaction
    def top_up_balance(session, amount):

        # Many threads could modify this account simultanously,
        # as incrementing the value in application code is
        # not atomic
        acc = session.query(Account).get(1)
        acc.balance += amount

    # Execute the conflict sensitive code inside a transaction aware code block
    top_up_balance(100)

Rules and limitations
-----------------------

The rules:

- You must not blindly swallow all exceptions (generic Python ``Exception``) within ``managed_transactions``. Example how to handle exceptions if generic exception catching is needed::

    # Create a decorated function which can try to re-run itself in the case of conflict
    @conflict_resolver.managed_transaction
    def myfunc(session):

        try:
            my_code()
        except Exception as e:
            if ConflictResolver.is_retryable_exception(e):
                # This must be passed to the function decorator, so it can attempt retry
                raise
            # Otherwise the exception is all yours

- Use special read-only database sessions if you know you do not need to modify the database and you need weaker transaction guarantees e.g. for displaying the total balance.

- Never do external actions, like sending emails, inside ``managed_transaction``. If the database transaction is replayed, the code is run twice and you end up sending the same email twice.

- Managed transaction code block should be as small and fast as possible to avoid transaction conflict congestion. Avoid long-running transactions by splitting up big transaction to smaller worker batches.

Compatibility
--------------

ConflictResolver should be compatible with all SQL databases providing Serializable isolation level. However, because Python SQL drivers and SQLAlchemy do not standardize the way how SQL execution communicates the transaction conflict back to the application, the exception mapping code might need to be updated to handle your database driver.

API documentation
------------------

See *ConflictResolver* API documentation below.

"""

import warnings
import logging
from collections import Counter

from sqlalchemy.orm.exc import ConcurrentModificationError
from sqlalchemy.exc import OperationalError
from sqlalchemy.exc import DBAPIError


UNSUPPORTED_DATABASE = "Seems like we might know how to support serializable transactions for this database. We don't know or it is untested. Thus, the reliability of the service may suffer. See transaction documentation for the details."

#: Tuples of (Exception class, test function). Behavior copied from _retryable_errors definitions copied from zope.sqlalchemy
DATABASE_COFLICT_ERRORS = []

try:
    import psycopg2.extensions
except ImportError:
    pass
else:
    DATABASE_COFLICT_ERRORS.append((psycopg2.extensions.TransactionRollbackError, None))

# ORA-08177: can't serialize access for this transaction
try:
    import cx_Oracle
except ImportError:
    pass
else:
    DATABASE_COFLICT_ERRORS.append((cx_Oracle.DatabaseError, lambda e: e.args[0].code == 8177))

if not DATABASE_COFLICT_ERRORS:
    # TODO: Do this when cryptoassets app engine is configured
    warnings.warn(UNSUPPORTED_DATABASE, UserWarning, stacklevel=2)

#: XXX: We need to confirm is this the right way for MySQL, SQLIte?
DATABASE_COFLICT_ERRORS.append((ConcurrentModificationError, None))


logger = logging.getLogger(__name__)


class ConflictResolver:
    """Helper class to resolve transaction conflicts in graceful manner.
    """

    def __init__(self, session_factory, retries):
        """
        :param session_factory: `callback()` which will give us a new SQLAlchemy session object for each transaction and retry

        :param retries: The number of attempst we try to re-run the transaction in the case of transaction conflict.
        """
        self.retries = retries

        self.session_factory = session_factory

        # Simple beancounting diagnostics how well we are doing
        self.stats = Counter(success=0, retries=0, errors=0, unresolved=0)

    @classmethod
    def is_retryable_exception(self, e):
        """Does the exception look like a database conflict error?

        Check for database driver specific cases.

        :param e: Python Exception instance
        """

        # TODO: OpertionalError raised locally, DBAPIError on Drone.IO
        # What's difference between these two SQL set ups?
        if not isinstance(e, (OperationalError, DBAPIError)):
            # Not an SQLAlchemy exception
            return False

        # The exception SQLAlchemy wrapped
        orig = e.orig

        for err, func in DATABASE_COFLICT_ERRORS:
            # EXception type matches, now compare its values
            if isinstance(orig, err):
                if func:
                    return func(e)
                else:
                    return True

        return False

    def managed_transaction(self, func):
        """Function decorator for SQL Serialized transaction conflict resolution through retries.

        ``managed_transaction`` decorator will retry to run the decorator function. Retries are attempted until ``ConflictResolver.retries`` is exceeded, in the case the original SQL exception is let to fall through.

        Please obey the rules and limitations of transaction retries in the decorated functions.
        """

        def decorated_func(*args, **kwargs):

            # Read attemps from app configuration
            attempts = self.retries

            session = self.session_factory()

            while attempts >= 0:

                try:
                    result = func(session, *args, **kwargs)
                    session.commit()
                    self.stats["success"] += 1
                    return result

                except Exception as e:

                    session.rollback()

                    if self.is_retryable_exception(e):
                        self.stats["retries"] += 1
                        attempts -= 1
                        if attempts < 0:
                            self.stats["unresolved"] += 1
                            raise CannotResolveDatabaseConflict("Could not replay the transaction {} even after {} attempts".format(func, self.retries)) from e
                        continue
                    else:
                        self.stats["errors"] += 1
                        # All other exceptions should fall through
                        raise

        # Make tracebacks friendlier
        decorated_func.__name__ = "{} wrapped by managed_transaction".format(func.__name__)

        return decorated_func

    def managed_non_retryable_transaction(self, func):
        """Provide ``managed_transactions`` decorator API compatibility without retrying.

        Decorate your transaction handling functions with this method if you absolute must not run the code twice for transaction retry and the user error is desirable outcome.
        """

        def decorated_func(*args, **kwargs):

            session = self.session_factory()

            try:
                result = func(session, *args, **kwargs)
                session.commit()
                self.stats["success"] += 1
                return result

            except Exception as e:

                session.rollback()

                if self.is_retryable_exception(e):
                    self.stats["unresolved"] += 1
                    raise CannotResolveDatabaseConflict("Cannot attempt to retry the transaction {}".format(func)) from e
                else:
                    self.stats["errors"] += 1
                    # All other exceptions should fall through
                    raise

        # Make tracebacks friendlier
        decorated_func.__name__ = "{} wrapped by managed_transaction".format(func.__name__)

        return decorated_func

    def transaction(self):
        """Get a transaction contextmanager instance using the conflict resolver session.

        This approach **does not** support conflict resolution, because Python context managers don't support looping. Instead, it will let any exception fall through. ``ConflictResolver.transaction`` is only useful to access the configured SQLAlchemy session in easy manner.

        * Useful for unit testing

        * Useful for shell sessions

        Transaction handling

        * Transaction is committed if the context manager exists succesfully

        * Transaction is rolled back on an exception

        Example::

            conflict_resolver = ConflictResolver(create_session, retries=3)
            with conflict_resolver.transaction() as session:
                account = session.query(Account).get(1)
                account.balance += 1

        """
        return ContextManager(self)


class CannotResolveDatabaseConflict(Exception):
    """The managed_transaction decorator has given up trying to resolve the conflict.

    We have exceeded the threshold for database conflicts. Probably long-running transactions or overload are blocking our rows in the database, so that this transaction would never succeed in error free manner. Thus, we need to tell our service user that unfortunately this time you cannot do your thing.
    """


class ContextManager:

    def __init__(self, conflict_resolver):
        self.conflict_resolver = conflict_resolver

    def __enter__(self):
        self.session = self.conflict_resolver.session_factory()
        return self.session

    def __exit__(self, exc_type, exc_value, traceback):
        if exc_type:
            self.session.rollback()
        else:
            self.session.commit()
