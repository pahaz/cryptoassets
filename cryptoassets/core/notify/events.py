


def create_txupdate(transaction, txid, account, address, amount, **extra):
    """txupdate event reports updates on incoming tranactions.

    :param transaction: Database transaction id as int

    :param txid: Network transaction id (transaction hash) as a string

    :param account: Database account id as int

    :param amount: How much this txupdate is worth of, as Decimal

    :param extra: Any cryptoasset specific data, e.g. ``confirmations`` in the case of mined coins

    :return: tuple "txupdate", data
    """
    assert type(address) == str
    assert type(account) == int
    assert type(transaction) == int
    assert amount
    assert amount > 0
    data = dict(transaction=transaction, txid=txid, account=account, address=address, amount=amount)
    data.update(extra)
    return "txupdate", data
