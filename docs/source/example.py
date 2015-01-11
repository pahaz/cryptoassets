"""cryptoassets.core example application.
"""

from decimal import Decimal

from cryptoassets.core.app import CryptoAssetsApp
from cryptoassets.core.app import Subsystem
from cryptoassets.core.configure import Configurator

from cryptoassets.core.utils.httpeventlistener import simple_http_event_listener

assets_app = CryptoAssetsApp()

# This will load the configuration file for the cryptoassets framework
configurer = Configurator(assets_app)
configurer.load_yaml_file("example.config.yaml")

# This will set up SQLAlchemy database connections, as loaded from
# config. It's also make assets_app.conflict_resolver available for us
assets_app.setup_session()


# This function will be run in its own background thread,
# where it runs mini HTTP server to receive and process
# any events which cryptoassets service sends to our
# process
@simple_http_event_listener(configurer.config)
def handle_cryptoassets_event(event_name, data):
    if event_name == "txupdate" and data["transaction_type"] == "deposit":
        address = data["address"]
        confirmations = data["confirmations"]
        txid = data["txid"]
        print("Got incoming transaction {} to address {}, {} confirmations".
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

    account = wallet.get_or_create_account_by_name("my account")

    # If we don't have any receiving addresses, create a default one
    if len(account.receiving_addresses) == 0:
        wallet.create_receiving_address(account)

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
    #: All addresses must have unique label (makes accounting easier)
    wallet.create_receiving_address(my_account)


@assets_app.conflict_resolver.managed_transaction
def send_to(session, address, amount):
    """Perform the actual send operation within managed transaction."""
    wallet, my_account = get_wallet_and_account()
    transaction = wallet.send(my_account, address, amount)
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

    send_to(address, amount)


@assets_app.conflict_resolver.managed_transaction
def print_status(session):
    """
    """
    wallet, account = get_wallet_and_account(session)

    # Get hold of classes we use for modelling Bitcoin
    # These are instances of
    #
    Address = assets_app.coins.get("btc").address_model
    Transaction = assets_app.coins.get("btc").transaction_model

    print("Welcome to cryptoassets example app")
    print("")
    print("You have the following addresses receiving addresses:")
    for address in session.query(Address).filter_by(account == account):
        print("{}: total received {} BTC", address.address, address.balance)
    print("")
    print("We know about the following transactions:")
    for tx in session.query(Transaction):
        if tx.state in ("pending", "broadcasted"):
            print("Outgoing tx #{} {} to {} network txid {} amount {} BTC".format(
                tx.id, tx.state, tx.txid, tx.address, tx.amount))
        elif tx.state in ("incoming", "processed"):
            print("Incoming tx #{} {} to {} network txid {} amount {} BTC".format(
                tx.id, tx.state, tx.txid, tx.address, tx.amount))
        else:
            print("Internal/other tx #{} {} amount {} BTC".format(
                tx.id, tx.state, tx.txid, tx.address, tx.amount))

    print("")
    print("Give a command")
    print("1) Create new receiving address")
    print("2) Send bitcoins to other address")
    print("3) Quit")


running = True
while running:

    print_status()
    command = raw_input("Give your command [1-3]:")
    if command == "1":
        create_receiving_address()
    elif command == "2":
        send()
    elif command == "3":
        running = False
    else:
        print("Unknown command!")
