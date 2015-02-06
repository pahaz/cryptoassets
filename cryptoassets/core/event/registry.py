
import logging


logger = logging.getLogger(__name__)


class EventHandlerRegistry:
    """Maintain list of active event_handler_registry.
    """

    def __init__(self):
        self.registry = {}

    def register(self, name, notifier):
        """Register a notifier to be fired for new transaction events.

        :param name: Any name you can refer later

        :param notifier: Instance of :py:class:`cryptocurrency.core.event_handler_registry.base.Notifier`.
        """
        self.registry[name] = notifier

    def get_all(self):
        return self.registry.values()

    def clear(self):
        self.registry.clear()

    def trigger(self, event_name, data):
        """Post an event to all listeners.

        If any of the event handlers fails with an exception, log the exception and continue processing the event.
        """
        handlers = self.get_all()
        for instance in handlers:
            logger.info("Posting event %s to notification handler %s", event_name, instance)
            try:
                instance.trigger(event_name, data)
            except Exception as e:
                # Do not let the event handler take us down
                logger.error("Error calling event handler %s for event %s", instance, event_name)
                logger.exception(e)

        if len(handlers) == 0:
            logger.warn("No registered transaction notfication handlers")
