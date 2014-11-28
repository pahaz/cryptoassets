"""Notify clients from new payments.

"""
import logging

from . import registry


logger = logging.getLogger(__name__)


def notify(event_name, data):
    """
    """
    handlers = registry.get_all()
    for instance in handlers:
        logger.info("Posting event %s to notification handler %s", event_name, instance)
        instance.trigger(event_name, data)

    if len(handlers) == 0:
        logger.warn("No registered transaction notfication handlers")
