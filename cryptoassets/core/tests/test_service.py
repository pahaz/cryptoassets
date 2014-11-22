"""Test posting notifications.

"""
import io
import os
import stat
import unittest
import json
import threading
import warnings

from cryptoassets.core.service.main import Service

from .. import configure
from ..notify import notify


class ServiceTestCase(unittest.TestCase):
    """Test that we can wind up our helper service.
    """

    def test_start_shutdown_service(self):
        """See that service starts and stops with bitcoind config.
        """

        test_config = os.path.join(os.path.dirname(__file__), "bitcoind.config.yaml")
        self.assertTrue(os.path.exists(test_config), "Did not found {}".format(test_config))
        config = configure.prepare_yaml_file(test_config)

        service = Service(config)
        service.start()



