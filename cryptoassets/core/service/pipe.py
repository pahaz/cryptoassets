"""Named pipe handler.

Handle incoming tx status as reading from named UNIX pipes.

This is more flexible than running a shell command, as you can do in-process handling of incoming transactions, making it suitable for unit testing and such.
"""

import os
import logging
import fcntl
import time

from cryptoassets.core.backend import registry


logger = logging.getLogger(__name__)


# Courtesy of http://code.activestate.com/recipes/578900-non-blocking-readlines/
def nonblocking_readlines(fd):
    """Generator which yields lines from F (a file object, used only for
       its fileno()) without blocking.  If there is no data, you get an
       endless stream of empty strings until there is data again (caller
       is expected to sleep for a while).
       Newlines are normalized to the Unix standard.
    """

    #fd = f.fileno()
    fl = fcntl.fcntl(fd, fcntl.F_GETFL)
    fcntl.fcntl(fd, fcntl.F_SETFL, fl | os.O_NONBLOCK)
    enc = "utf-8"

    buf = bytearray()
    while True:
        try:
            block = os.read(fd, 8192)
        except BlockingIOError:
            yield ""
            continue

        if not block:
            if buf:
                yield buf.decode(enc)
                buf.clear()
            break

        buf.extend(block)

        while True:
            r = buf.find(b'\r')
            n = buf.find(b'\n')
            if r == -1 and n == -1: break

            if r == -1 or r > n:
                yield buf[:(n+1)].decode(enc)
                buf = buf[(n+1):]
            elif n == -1 or n > r:
                yield buf[:r].decode(enc) + '\n'
                if n == r+1:
                    buf = buf[(r+2):]
                else:
                    buf = buf[(r+1):]


class PipedWalletNotifyHandler:
    """Handle walletnofify notificatians from bitcoind through named UNIX pipe."""

    def __init__(self, transaction_updater, fname, mode=0o703):
        """
        :param transaction_updater: Instance of :py:class:`cryptoassets.core.backend.bitcoind.TransactionUpdater` or None

        :param name: Full path to the UNIX named pipe

        :param mode: Octal UNIX file mode for the named pipe
        """
        self.transaction_updater = transaction_updater
        self.running = True
        self.fname = fname
        self.ready = False
        self.mode = mode

    def handle_tx_update(self, txid):
        if self.transaction_updater:
            self.transaction_updater.handle_wallet_notify(txid)

    def run(self):

        reader = None

        try:
            # Clean up previous run
            if os.path.exists(self.fname):
                os.remove(self.fname)

            os.mkfifo(self.fname, self.mode)

            assert os.path.exists(self.fname)

            fd = os.open(self.fname, os.O_RDONLY | os.O_NONBLOCK)

            self.ready = True

            while self.running:
                for line in nonblocking_readlines(fd):
                    if line:
                        txid = line.strip()
                        self.handle_tx_update(txid)
                time.sleep(0.1)

        except Exception as e:
            logger.error("walletnofify error")
            logger.exception(e)

        finally:
            if reader:
                os.close(reader)

            os.unlink(self.fname)

    def stop(self):
        self.running = False
