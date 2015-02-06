"""blockchain.info backend.

**The support is disabled in this version**
"""

import json
import logging

import requests


URL = "https://blockchain.info/"

logger = logging.getLogger(__name__)


#: What blockchain.info charges us for outgoing transactions
BLOCKCHAIN_NETWORK_FEE = 1000


class BlockChainAPIError(Exception):
    pass


class BlockChain:
    """XXX: Unsupported"""

    def __init__(self, identifier, password):
        """
        """
        self.identifier = identifier
        self.password = password

    def create_address(self, label):
        params = {
            "label": label,
            "password": self.password
        }

        url = URL + "merchant/%s/new_address" % self.identifier

        r = requests.get(url, params=params)
        data = r.json()
        return data["address"]

    def get_all_address_data(self):
        """ Return the balances of all addresses in the format:

        https://blockchain.info/api/blockchain_wallet_api
        """

        params = {
            "password": self.password
        }

        url = URL + "merchant/%s/list" % self.identifier

        r = requests.get(url, params=params)
        data = r.json()

        if "error" in data:
            logger.error("Bad reply from blockchain.info %s", data)
            raise BlockChainAPIError(data["error"])
        if "addresses" not in data:
            logger.error("Bad reply from blockchain.info %s", data)
            raise BlockChainAPIError("Did not get proper reply")
        else:
            for address in data["addresses"]:
                yield address

    def get_balances(self, addresses):
        """ Get balances on multiple addresses.
        """

        assert type(addresses) == list

        # {'total_received': 1000000, 'balance': 1000000, 'label': None, 'address': '1tELc3NxVp2PosFUzn9izG2Him9G8uKdp'}
        # {'total_received': 0, 'balance': 0, 'label': 'Test address 1413841830.468295', 'address': '1KwDRh1tN1v9p6NnR8xxaJG1Zbg7DmydKX'}
        address_data = self.get_all_address_data()
        for entry in address_data:
            if entry["address"] in addresses:
                yield entry["address"], int(entry["balance"])

    def send(self, recipients):
        """
        :param recipients: Dict of (address, satoshi amount)
        """

        params = {
            "password": self.password,
            "recipients": json.dumps(recipients)
        }

        url = URL + "merchant/%s/sendmany" % self.identifier

        r = requests.get(url, params=params)
        data = r.json()

        if "error" in data:
            raise BlockChainAPIError("Could not send the transaction: {}".format(data["error"]))

        return data["tx_hash"], BLOCKCHAIN_NETWORK_FEE

    def receive(self, receiver, amount):
        """
        """






