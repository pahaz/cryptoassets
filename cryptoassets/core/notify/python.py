"""In-process Python notifications for transaction updates.
"""
import requests
import logging
import json

from .base import Notifier
from zope.dottedname.resolve import resolve

logger = logging.getLogger(__name__)


class InProcessNotifier(Notifier):
    """Do a in-process Python callback for incoming transaction notifications.

    """

    def __init__(self, callback):
        """
        :param callback: A dotted name to Python callback function fn(event_name, data) which will be called upon a notification. ``event_name`` is a string, ``data`` is a dict.
        """
        self.callback_dotted_name = callback

    def trigger(self, event_name, data):
        assert type(event_name) == str
        func = resolve(self.callback_dotted_name)
        func(event_name, data)
