"""cryptoassets.core example application"""

import os
import warnings
from decimal import Decimal
import datetime


from sqlalchemy.exc import SAWarning

from cryptoassets.core.app import CryptoAssetsApp
from cryptoassets.core.configure import Configurator
from cryptoassets.core.utils.httpeventlistener import simple_http_event_listener
from cryptoassets.core.models import NotEnoughAccountBalance

# Because we are using a toy database and toy money, we ignore this SQLLite database warning
warnings.filterwarnings(
    'ignore',
    r"^Dialect sqlite\+pysqlite does \*not\* support Decimal objects natively\, "
    "and SQLAlchemy must convert from floating point - rounding errors and other "
    "issues may occur\. Please consider storing Decimal numbers as strings or "
    "integers on this platform for lossless storage\.$",
    SAWarning, r'^sqlalchemy\.sql\.type_api$')


assets_app = CryptoAssetsApp()

# This will load the configuration file for the cryptoassets framework
# for the same path as examply.py is
conf_file = os.path.join(os.path.dirname(__file__), "example.config.yaml")
configurer = Configurator(assets_app)
configurer.load_yaml_file(conf_file)

# This will set up SQLAlchemy database connections, as loaded from
# config. It's also make assets_app.conflict_resolver available for us
assets_app.setup_session()


# This function will be run in its own background thread,
# where it runs mini HTTP server to receive and process
# any events which cryptoassets service sends to our
# process
@simple_http_event_listener(configurer.config)
def handle_cryptoassets_event(event_name, data):
    if event_name == "txupdate":
        address = data["address"]
        confirmations = data["confirmations"]
        txid = data["txid"]
        print("Got transaction notification txid:{} addr:{}, confirmations:{}".
            format(txid, address, confirmations))


def get_wallet_and_account(session):
    """Return or create instances of the default wallet and accout.

    :return: Tuple (BitcoinWallet instance, BitcoinAccount instance)
    """

    # This returns the class cryptoassets.core.coins.bitcoin.models.BitcoinWallet.
    # It is a subclass of cryptoassets.core.models.GenericWallet.
    # You can register several of cryptocurrencies to be supported within your application,
    # but in this example we use only Bitcoin.
    WalletClass = assets_app.coins.get("btc").wallet_model

    # One application can have several wallets.
    # Within a wallet there are several accounts, which can be
    # user accounts or automated accounts (like escrow).
    wallet = WalletClass.get_or_create_by_name("default wallet", session)
    session.flush()

    account = wallet.get_or_create_account_by_name("my account")
    session.flush()

    # If we don't have any receiving addresses, create a default one
    if len(account.addresses) == 0:
        wallet.create_receiving_address(account, automatic_label=True)

    return wallet, account


# Every time you access cryptoassets database it must happen
# in sidea managed transaction function.
#
# Use ConflictResolevr.managed_transaction decoreator your function gets an extra
# ``session`` argument as the first argument. This is the SQLAlchemy
# database session you should use to  manipulate the database.
#
# In the case of a database transaction conflict, ConflictResolver
# will rollback code in your function and retry again.
#
# For more information see
# http://cryptoassetscore.readthedocs.org/en/latest/api/utils.html#transaction-conflict-resolver
#
@assets_app.conflict_resolver.managed_transaction
def create_receiving_address(session):
    """Create new receiving address on the default wallet and account."""
    wallet, my_account = get_wallet_and_account(session)

    # All addresses must have unique label on block.io.
    # Note that this is not a limitation of Bitcoin,
    # but block.io service itself.
    wallet.create_receiving_address(my_account, automatic_label=True)


@assets_app.conflict_resolver.managed_transaction
def send_to(session, address, amount):
    """Perform the actual send operation within managed transaction."""
    wallet, my_account = get_wallet_and_account(session)
    friendly_date = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S")
    transaction = wallet.send(my_account, address, amount, "Test send at {}".format(friendly_date))
    print("Created new transaction #{}".format(transaction.id))


def send():
    """Ask how many BTCTEST bitcoins to send and to which address."""
    address = input("Give the bitcoin TESTNET address where you wish to send the bitcoins:")
    amount = input("Give the amount in BTC to send:")

    try:
        amount = Decimal(amount)
    except ValueError:
        print("Please enter a dot separated decimal number as amount.")
        return

    try:
        send_to(address, amount)
    except NotEnoughAccountBalance:
        print("*" * 40)
        print("Looks like your wallet doesn't have enough Bitcoins to perform the send. Please top up your wallet from testnet faucet.")
        print("*" * 40)


@assets_app.conflict_resolver.managed_transaction
def print_status(session):
    """Print the state of our wallet and transactions."""
    wallet, account = get_wallet_and_account(session)

    # Get hold of classes we use for modelling Bitcoin
    # These classes are defined in cryptoassets.core.coin.bitcoind.model models
    Address = assets_app.coins.get("btc").address_model
    Transaction = assets_app.coins.get("btc").transaction_model

    print("Account #{}, confirmed balance {:.8f} BTC, incoming BTC {:.8f}". \
        format(account.id, account.balance, account.get_unconfirmed_balance()))

    print("")
    print("Receiving addresses available:")
    print("(Send Testnet Bitcoins to them to see what happens)")

    for address in session.query(Address).filter(Address.account == account):
        print("- {}: confirmed received {:.8f} BTC".format(address.address, address.balance))
    print("")
    print("We know about the following transactions:")
    for tx in session.query(Transaction):
        if tx.state in ("pending", "broadcasted"):
            print("Outgoing tx #{} {} to {} network txid {} amount {} BTC".format(
                tx.id, tx.state, tx.txid, tx.address, tx.amount))
        elif tx.state in ("incoming", "processed"):
            print("- IN tx:{} to:{} amount:{:.8f} BTC confirmations:{}".format(
                tx.txid, tx.address.address, tx.amount, tx.confirmations))
        else:
            print("Internal/other tx #{} {} amount {} BTC".format(
                tx.id, tx.state, tx.txid, tx.address, tx.amount))

    print("")
    print("Give a command")
    print("1) Create new receiving address")
    print("2) Send bitcoins to other address")
    print("3) Quit")


print("Welcome to cryptoassets example app")
print("")

running = True
while running:

    print_status()
    command = input("Give your command [1-3]:")
    print("")
    if command == "1":
        create_receiving_address()
    elif command == "2":
        send()
    elif command == "3":
        running = False
    else:
        print("Unknown command!")
