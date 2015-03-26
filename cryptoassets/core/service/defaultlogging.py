"""Default logging settings."""

import os
import logging
import sys

from rainbow_logging_handler import RainbowLoggingHandler


def setup_stdout_logging():
    formatter = logging.Formatter("[%(asctime)s] [%(name)s %(funcName)s] %(message)s")  # same as default

    # setup `RainbowLoggingHandler`
    # and quiet some logs for the test output
    handler = RainbowLoggingHandler(sys.stdout)
    handler.setFormatter(formatter)
    logger = logging.getLogger()
    logger.handlers = [handler]
    #logger.addHandler(handler)

    if "VERBOSE" in os.environ:
        logger.setLevel(logging.DEBUG)
    else:
        logger.setLevel(logging.INFO)

    logger = logging.getLogger("requests.packages.urllib3.connectionpool")
    logger.setLevel(logging.ERROR)

    logger = logging.getLogger("cryptoassets.core.backend.blockio")
    logger.setLevel(logging.WARN)

    logger = logging.getLogger("cryptoassets.core.backend.bitcoind")
    logger.setLevel(logging.WARN)

    logger = logging.getLogger("apscheduler")
    logger.setLevel(logging.WARN)

    # SQL Alchemy transactions
    logger = logging.getLogger("txn")
    logger.setLevel(logging.ERROR)
