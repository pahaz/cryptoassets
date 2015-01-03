
import logging


logger = logging.getLogger(__name__)


class NotifierRegistry:
    """Maintain list of active notifiers.
    """

    def __init__(self):
        self.registry = {}

    def register(self, name, notifier):
        """Register a notifier to be fired for new transaction events.

        :param name: Any name you can refer later

        :param notifier: Instance of :py:class:`cryptocurrency.core.notifiers.base.Notifier`.
        """
        self.registry[name] = notifier

    def get_all(self):
        return self.registry.values()

    def clear(self):
        self.registry.clear()

    def notify(self, event_name, data):
        """Post an event to all listeners.
        """
        handlers = self.get_all()
        for instance in handlers:
            logger.info("Posting event %s to notification handler %s", event_name, instance)
            instance.trigger(event_name, data)

        if len(handlers) == 0:
            logger.warn("No registered transaction notfication handlers")
