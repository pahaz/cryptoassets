"""Import existing wallet balance to the accounting.

If you have a wallet in some service and you wish to use it with *cryptoassets.core*, you need to tell *cryptoassets.core* what to do with the existing balance in the wallet, from the time before the wallet was managed by *cryptoassets.core*.

This is especially useful for testing. To run unit tests you need to have some cryptocurrency balance somewhere. You have known backends which you configure the unit tests to connect to. These backends have default wallets and there is some balance on these wallets, so unit tests can perform withdraw tests.
"""
import datetime
import logging


from sqlalchemy.orm.session import Session


logger = logging.getLogger(__name__)


def has_unaccounted_balance(backend, wallet):

    balance = backend.get_backend_balance()
    if balance > wallet.balance:
        return True
    elif balance < wallet.balance:
        raise RuntimeError("We have more coins on our accounts than the backend has balance.")
    else:
        return False


def create_import_transaction(amount, account):
    """Put wallet extra coins, for which we do not know the owner, on a specific account.

    Execute inside transaction manager.

    :param Decimal amount: How many extra coins to account

    :param account: Account instance where to put coins
    """

    assert amount > 0
    assert account.id
    assert account.wallet

    session = Session.object_session(account)

    Transaction = account.coin_description.Transaction
    wallet = account.wallet

    all_imports = session.query(Transaction).filter(Transaction.receiving_account == account, Transaction.state == "balance_import")
    counted = all_imports.count()

    t = Transaction()
    t.sending_account = None
    t.receiving_account = account
    t.wallet = wallet
    t.amount = amount
    t.state = "balance_import"
    t.credited_at = datetime.datetime.utcnow()
    t.label = "Backend balance import #{}".format(counted+1)
    session.add(t)

    logger.info("Imported balance %s to account %d", amount, account.id)

    account.balance += amount
    wallet.balance += amount


def import_unaccounted_balance(backend, wallet, account):
    """Creates a new transaction which will put all assets in the wallet on a new account."""

    assert account.wallet.id == wallet.id

    logger.debug("Importing balance from backend %s", backend)

    balance = backend.get_backend_balance()
    if balance == 0:
        logger.debug("Backend has zero balance")

    if balance > wallet.balance:
        logger.debug("Creating import transaction")
        create_import_transaction(balance - wallet.balance, account)
    elif balance < wallet.balance:
        raise RuntimeError("We have more coins on our accounts than the backend has balance.")
    else:
        # Our accounting and backend balance match
        logger.debug("Backend balance is sync with the wallet")
        return
