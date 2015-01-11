import unittest

from zope.dottedname.resolve import resolve

from ..coin import defaults
from ..coin import registry
from ..backend.null import DummyCoinBackend

from . import testlogging
from . import testwarnings


class ValidatorTestCase(unittest.TestCase):
    """Test validating different addresses"""

    def setUp(self):
        testlogging.setup()
        testwarnings.begone()

    def load_default_coin(self, name, testnet):
        """Setups a CoinRegistry with one coin and null backend.
        """

        default_models_module = defaults.COIN_MODEL_DEFAULTS.get(name)
        coin_description = resolve(default_models_module).coin_description

        coin = registry.Coin(coin_description, None, testnet=testnet)
        return coin

    def tearDown(self):
        pass

    def test_bitcoin(self):
        btc = self.load_default_coin("btc", False)
        self.assertTrue(btc.validate_address("1HHHoqFc4qNXs61zYCFgDmT8sDzzxFaFQq"))

        btctest = self.load_default_coin("btc", True)
        self.assertTrue(btctest.validate_address("mvCounterpartyXXXXXXXXXXXXXXW24Hef"))

        btctest = self.load_default_coin("btc", True)
        self.assertFalse(btctest.validate_address("ZZCounterpartyXXXXXXXXXXXXXXW24Hef"))

    def test_dogecoin(self):
        doge = self.load_default_coin("doge", False)
        self.assertTrue(doge.validate_address("DT8gpWajoMN1MSyfg7Wocgv7L92UD4MBAo"))

        dogetest = self.load_default_coin("doge", True)
        self.assertTrue(dogetest.validate_address("2MvwwC1ksh5Qre5iaT2pKgmGopbPXFuu2V1"))

    def test_applebyte(self):
        aby = self.load_default_coin("aby", False)
        self.assertTrue(aby.validate_address("AdvQ8uMzcZk7D4HkiovSw63WiHQUSviifU"))
        self.assertFalse(aby.validate_address("xxx"))

    def test_litecoin(self):
        ltc = self.load_default_coin("ltc", False)
        self.assertTrue(ltc.validate_address("LiWVRt7ZQPoYcfM9jyYMNSHzPzRaW7dYLg"))

        ltc = self.load_default_coin("ltc", True)
        self.assertTrue(ltc.validate_address("2N6p5ChbhjynjQnyrpEPWdCirkRk5b8b19u"))
