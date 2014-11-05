"""Distributed lock management.
"""

import threading

_locks = {}


def create_thread_lock(name):
    if name not in _locks:
        _locks[name] = threading.Lock()

    return _locks[name]


def configure():
    pass


def get_or_create_lock(name):
    return create_thread_lock(name)