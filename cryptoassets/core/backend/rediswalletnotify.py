"""Use Redis pubsub for walletnotify notifications.

`Redis <http://redis.io>`_ offers mechanism called `pubsub <http://redis.io/topics/pubsub>`_ for channeled communication which can be used e.g. for interprocess communications.


1. Connects to a Redis database over authenticated conneciton

2. Opens a pubsub connection to a specific channel

3. bitcoind walletnofify writes notifies to this channel using ``redis-cli`` command line tool

4. This thread reads pubsub channel, triggers the service logic on upcoming notify

Example `walletnotify` line::

    walletnotify=redis-cli publish bitcoind_walletnotify_pubsub %self

To install Redis on bitcoind server::

    apt-get install redis-server redis-tools

.. warning::

    The Redis authenticated connection is not encrypted. Use VPN or SSH tunnel to connect Redis over Internet.

Options
-------

:param class: Always ``cryptoassets.core.backend.rediswalletnotify.RedisWalletNotifyHandler``

:param host: IP/domain where Redis is running, default is ``localhost``.

:param port: TCP/IP port Redis is listetning to

:param db: Redis database number

:param username: optional username

:param password: optional password

:param channel: Name of Redis pubsub channel where we write transaction txids, default ``bitcoind_walletnotify_pubsub``
"""

import logging
import threading
import time

import redis

from .base import IncomingTransactionRunnable


logger = logging.getLogger(__name__)


class RedisWalletNotifyHandler(threading.Thread, IncomingTransactionRunnable):
    """Post Bitcoind walletnotifys over authenticated Redis connection."""

    def __init__(self, transaction_updater, host="localhost", port=6379, password=None, db=0, channel="bitcoind_walletnotify_pubsub"):
        """Configure a HTTP wallet notify handler server.
        """

        self.host = host
        self.port = int(port)
        self.password = password
        self.db = int(db)
        self.channel = channel
        self.running = False
        self.transaction_updater = transaction_updater
        # Diagnostics
        self.message_count = 0
        threading.Thread.__init__(self)

    def handle_tx_update(self, txid):
        self.transaction_updater.handle_wallet_notify(txid)

    def run(self):

        try:

            client = redis.StrictRedis(host=self.host, port=self.port, db=self.db, password=self.password)
            pubsub = client.pubsub()
            pubsub.subscribe(self.channel)

            # TODO: Add reconnecting on error
            self.running = True

            while self.running:

                try:
                    message = pubsub.get_message()
                    if message and message["type"] == "message":
                        self.message_count += 1
                        txid = message.get("data")
                        txid = txid.decode("utf-8")
                        self.handle_tx_update(txid)
                    else:
                        time.sleep(1.0)

                except Exception as e:
                    pubsub.close()
                    logger.error("Redis pubsub listening aborted")
                    logger.exception(e)
                    break

            self.running = False

            pubsub.close()
        except Exception as e:
            logger.error("Redis could not connect/close")
            logger.exception(e)

    def stop(self):
        self.running = False
