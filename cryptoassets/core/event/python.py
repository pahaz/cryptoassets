"""In-process Python event handling.

Run Python function each time event occures. This assumes you have your Python application code in the same virtualenv as *cryptoassets.core* is. The code is executed directly within :doc:`cryptoassets helper service </service>` process.

Configuration options

:param class: Always ``cryptoassets.core.event.python.InProcessEventHandler``.

:param callback: A dotted name to Python callback function fn(event_name, data) which will be called upon a notification. ``event_name`` is a string, ``data`` is a dict.

"""
import logging

from .base import EventHandler
from zope.dottedname.resolve import resolve

logger = logging.getLogger(__name__)


class InProcessEventHandler(EventHandler):

    def __init__(self, callback):
        """
        """
        self.callback_dotted_name = callback

    def trigger(self, event_name, data):
        assert type(event_name) == str
        func = resolve(self.callback_dotted_name)
        func(event_name, data)
