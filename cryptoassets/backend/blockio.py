"""
    Block.Io wallet implementation.

    - All transactions are asynchronouos

    - Local cached data is kept on the server-side

"""

from slugify import slugify

from block_io import BlockIo as _BlockIo


class BlockIo:
    """ Synchronous block.io API. """

    def __init__(self, api_key, pin):
        """
        """
        self.block_io = _BlockIo(api_key, pin, 2)

    def create_address(self, label):
        """
        """

        # block.io does not allow arbitrary characters in labels
        # {'data': {'address': '2N2Qqvj5rXv27rS6b7rMejUvapwvRQ1ahUq', 'user_id': 5, 'label': 'slange11', 'network': 'BTCTEST'}, 'status': 'success'}
        label = slugify(label)
        result = self.block_io.get_new_address(label=label)
        assert result["status"] == "success"
        return result["data"]["address"]

    def addresses(self):
        """
        :return: List of addresses and their balances
        """

    def send(self, receiver, amount):
        """
        """

    def receive(self, receiver, amount):
        """
        """


class Poller:

