"""Send events to your application as HTTP POST request.

The HTTP POST contains two fields, ``event_name`` (string) and ``data`` (JSON).

Decimals are converted to strings for serialization.

Configuration options

:param class: Always ``cryptoassets.core.event.http.HTTPEventHandler``.

:param url: Do a HTTP POST to this URL on a new event. Example: ``http://localhost:30000``.
"""

import requests
import logging

from .base import EventHandler
from .base import event_json_dumps

logger = logging.getLogger(__name__)


class HTTPEventHandler(EventHandler):

    def __init__(self, url):
        self.url = url

    def trigger(self, event_name, data):
        assert type(event_name) == str

        data = event_json_dumps(data)

        resp = requests.post(self.url, data=dict(event_name=event_name, data=data, xdata=data))
        if resp.status_code != 200:
            logger.error("Failed to call HTTP hook %s, status code %d", self.url, resp.status_code)
        else:
            logger.info("Succesfully called HTTP hook %s", self.url)
