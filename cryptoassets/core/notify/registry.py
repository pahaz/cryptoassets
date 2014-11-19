"""Maintain list of active notifiers.
"""
_registry = {}


def register(name, notifier):
    """Register a notifier to be fired for new transaction events.

    :param name: Any name you can refer later

    :param notifier: Instance of :py:class:`cryptocurrency.core.notifiers.base.Notifier`.
    """
    _registry[name] = notifier


def get_all():
    return _registry.values()
