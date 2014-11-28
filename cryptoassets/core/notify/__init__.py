"""Notify clients from new payments.

"""
import logging

from . import registry


logger = logging.getLogger(__name__)


def notify(event_name, data):
    """
    """
    for instance in registry.get_all():
        logger.info("Posting event %s to notification handler %s", event_name, instance)
        instance.trigger(event_name, data)
    else:
        logger.warn("No registered transaction notfication handlers")
