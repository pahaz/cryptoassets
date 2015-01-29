"""Check for dangling threads at the end of the each test."""

import threading
import time


def check_dangling_threads(timeout=15):
    """Check if any Python threads are still alive after timeout and die with an exception if so."""
    deadline = time.time() + timeout
    while threading.active_count() > 1 and time.time() < deadline:
        time.sleep(1)

    if threading.active_count() > 1:
        threads = list(threading.enumerate())
        assert "Had extra threads alive at the end of the tests {}".format(threads)
