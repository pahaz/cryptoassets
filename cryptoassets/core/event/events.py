
def txupdate(coin_name, transaction, network_transaction, transaction_type, txid, account, address, amount, credited, **extra):
    """txupdate event reports the confirmation changes of incoming transaction (deposit) or outgoing transaction (broadcasted).

    This event is fired for each transaction, when its ``confirmations`` changes. One network transaction may contain several deposit or broadcast transactions and they all trigger the event.

    When the incoming transaction is first seen in the network, but it is not yet confirmed, confirmations is 0. Evaluate the risk of `double spending <https://en.bitcoin.it/wiki/Double-spending>`_ for these kind of transactions in your application context.

    :param coin_name: Lowercase acronym name for this asset

    :param transaction: Id of :py:class:`cryptoasset.core.models.GenericTransaction` instance

    :param network_transaction: Id of :py:class:`cryptoasset.core.models.GenericNetworkTransaction` instance

    :param transaction_type: String ``deposit`` (incoming) or ``broadcast`` (outgoing)

    :param txid: Network transaction id (transaction hash) as a string

    :param account: Database account id as int, either receiving account (deposit) or sending account (broadcast)

    :param amount: How much the transaction is worth of, as Decimal

    :param credited: Has this transaction reaches system-set confirmation threshold

    :param extra: Any cryptoasset specific data as dict, e.g. ``dict(confirmations=0)`` in the case of mined coins

    :return: Event data as dict()
    """
    assert type(coin_name) == str
    assert type(address) == str
    assert type(account) == int, "Expected account id as int, got {}".format(account)
    assert type(transaction) == int
    assert type(network_transaction) == int
    assert type(transaction_type) == str
    assert amount
    assert amount > 0
    data = dict(transaction=transaction, network_transaction=network_transaction, txid=txid, account=account, address=address, amount=amount, credited=credited)
    data.update(extra)
    return data
