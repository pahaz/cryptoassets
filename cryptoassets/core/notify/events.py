


def create_txupdate(transaction, txid, account, address, amount, **extra):
    assert type(address) == str
    assert type(account) == int
    assert type(transaction) == int
    assert amount
    data = dict(transaction=transaction, txid=txid, account=account, address=address, amount=amount)
    data.update(extra)
    return "txupdate", data
