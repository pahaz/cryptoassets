"""Check for dangling threads at the end of the each test."""

import threading
import time


def check_dangling_threads():

    deadline = time.time() + 5
    while threading.active_count() > 1 and time.time() < deadline:
        time.sleep(1)

    if threading.active_count() > 1:
        threads = list(threading.threading.enumerate())
        assert "Had extra threads alive at the end of the tests {}".format(threads)
