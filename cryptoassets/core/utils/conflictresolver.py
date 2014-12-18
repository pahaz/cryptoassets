"""Serialized SQL transaction conflict resolution."""

import warnings
import logging
from collections import Counter

from sqlalchemy.orm.exc import ConcurrentModificationError
from sqlalchemy.exc import OperationalError


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


class CannotResolveDatabaseConflict(Exception):
    """The managed_transaction decorator has given up trying to resolve the conflict.

    We have exceeded the threshold for database conflicts. Probably long-running transactions or overload are blocking our rows in the database, so that this transaction would never succeed in error free manner. Thus, we need to tell our service user that unfortunately this time you cannot do your thing.
    """


class ConflictResolver:

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

        if not isinstance(e, OperationalError):
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
        """SQL Seralized transaction isolation-level conflict resolution.

        When SQL transaction isolation level is its highest level (Serializable), the SQL database itself cannot alone resolve conflicting concurrenct transactions. Thus, the SQL driver raises an exception to signal this condition.

        ``managed_transaction`` decorator will retry to run everyhing inside the function

        Usage:

            from decimal import Decimal

            from myapp import cryptoassetsapp

            def get_my_website_wallet(session):
                Wallet = cryptoassets.coins.get("btc").wallet_model
                wallet = Wallet.get_or_create_by_name("default", session)
                return wallet

            def my_stuff():

                coin = "btc"

                # We'll put the transaction sensitive code inside a closure function.
                # In the case there is a conflict error inside the function,
                # the tranaction manager tries to replay the code for X times
                # before giving up with CannotResolveDatabaseConflict

                @cryptoassetsapp.managed_transaction
                def transaction(session):

                    # You'll get SQLAlchemy session as the parameter to the function
                    wallet = get_my_website_wallet(session)
                    from_account = wallet.get_account_by_name("sender")
                    to_account = wallet.get_account_by_name("receiver")
                    wallet.send_internal(from_account, to_account, Decimal("1.0"), "test transfer")

                transaction()

        The rules:

        - You must not swallow all exceptions within ``managed_transactions``. Example how to handle exceptions::

            from cryptoassets.core.utils.transactionmanager import DATABASE_COFLICT_ERRORS

            try:
                my_code()
            except DATABASE_COFLICT_ERRORS as conflict:
                # We must always let conflict errors to fall through,
                # so that the underlying ``managed_transaction`` can retry
                raise
            except Exception as e:
                # Handle your exception
                pass

        - Use read-only database sessions if you know you do not need to modify the database and you need weaker transaction guarantees e.g. for displaying the total balance.

        - Never do external actions, like sending emails, inside ``managed_transaction``. If the database transaction is replayed, the code is run twice and you end up sending the same email twice.

        - Managed transaction section should be as small and fast as possible

        - Avoid long-running transactions by splitting up big transaction to smaller worker batches

        This implementation heavily draws inspiration from the following sources

        - https://gist.github.com/khayrov/6291557


        """

        def decorated_func():

            # Read attemps from app configuration
            attempts = self.retries

            while attempts >= 0:

                session = self.session_factory()
                try:
                    result = func(session)
                    session.close()
                    self.stats["success"] += 1
                    return result

                except Exception as e:
                    if self.is_retryable_exception(e):
                        session.close()
                        self.stats["retries"] += 1
                        attempts -= 1
                        if attempts < 0:
                            self.stats["unresolved"] += 1
                            raise CannotResolveDatabaseConflict("Could not replay the transaction {} even after {} attempts".format(func, self.retries)) from e
                        continue
                    else:
                        session.rollback()
                        self.stats["errors"] += 1
                        # All other exceptions should fall through
                        raise

        return decorated_func
