"""Python logging setup for unit test runs."""

import os
import logging
import sys

from rainbow_logging_handler import RainbowLoggingHandler


def setup():
    formatter = logging.Formatter("[%(asctime)s] %(name)s %(funcName)s():%(lineno)d\t%(message)s")  # same as default

    # setup `RainbowLoggingHandler`
    # and quiet some logs for the test output
    handler = RainbowLoggingHandler(sys.stderr)
    handler.setFormatter(formatter)
    logger = logging.getLogger()
    logger.addHandler(handler)

    if "VERBOSE_TEST" in os.environ:
        logger.setLevel(logging.DEBUG)
    else:
        logger.setLevel(logging.ERROR)

    logger = logging.getLogger("requests.packages.urllib3.connectionpool")
    logger.setLevel(logging.ERROR)

    logger = logging.getLogger("cryptoassets.core.backend.blockio")
    logger.setLevel(logging.DEBUG)

    logger = logging.getLogger("cryptoassets.core.backend.bitcoind")
    logger.setLevel(logging.WARN)

    # SQL Alchemy transactions
    logger = logging.getLogger("txn")
    logger.setLevel(logging.ERROR)
