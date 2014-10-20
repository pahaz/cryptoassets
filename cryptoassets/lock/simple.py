"""

    Simple locking implementatoin.

    Only safe for single process applications.

"""

import threading

_locks = {}


def create_thread_lock(name):
    if name not in _locks:
        _locks[name] = threading.Lock()

    return _locks[name]
