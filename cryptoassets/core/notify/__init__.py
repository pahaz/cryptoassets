"""Notify clients from new payments.

"""

from . import registry


def notify(event_name, data):
    """
    """
    for instance in registry.get_all():
        instance.trigger(event_name, data)

