
def txupdate(transaction, network_transaction, txid, account, address, amount, credited, **extra):
    """txupdate event reports updates on incoming tranactions.

    :param transaction: Id of :py:class:`cryptoasset.core.models.GenericTransaction` instance

    :param network_transaction: Id of :py:class:`cryptoasset.core.models.GenericNetworkTransaction` instance

    :param txid: Network transaction id (transaction hash) as a string

    :param account: Database account id as int

    :param amount: How much this txupdate is worth of, as Decimal

    :param credited: Has this transaction reaches system-set confirmation threshold

    :param extra: Any cryptoasset specific data, e.g. ``confirmations`` in the case of mined coins

    :return: tuple "txupdate", data
    """
    assert type(address) == str
    assert type(account) == int, "Expected account id as int, got {}".format(account)
    assert type(transaction) == int
    assert type(network_transaction) == int
    assert amount
    assert amount > 0
    data = dict(transaction=transaction, network_transaction=network_transaction, txid=txid, account=account, address=address, amount=amount, credited=credited)
    data.update(extra)
    return "txupdate", data
