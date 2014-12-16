"""Serialized SQL transaction conflict resolution."""

import warning

from sqlalchemy.orm.exc import ConcurrentModificationError
from sqlalchemy.exc import DBAPIError

UNSUPPORTED_DATABASE = "Seems like we might know how to support serializable transactions for this database. We don't know or it is untested. Thus, the reliability of the service may suffer. See transaction documentation for the details."

#: Behavior copied from _retryable_errors definitions copied from zope.sqlalchemy
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
    warning.warn(UNSUPPORTED_DATABASE, UserWarning, stacklevel=2)


DATABASE_COFLICT_ERRORS.append(ConcurrentModificationError)


class CannotResolveDatabaseConflict(Exception):
    """The managed_transaction decorator has given up trying to resolve the conflict.

    We have exceeded the threshold for database conflicts. Probably long-running transactions or overload are blocking our rows in the database, so that this transaction would never succeed in error free manner. Thus, we need to tell our service user that unfortunately this time you cannot do your thing.
    """


def managed_tranansaction(self, func):
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
    """







