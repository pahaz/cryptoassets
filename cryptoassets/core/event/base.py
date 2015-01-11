import abc


class EventHandler(abc.ABC):
    """Post information about new receivent payments and transactions across processes.
    """

    @abc.abstractmethod
    def trigger(self, event_name, data):
        """Notify about a new event.

        :param event_name: Event name as a string

        :param data: Related data as dictionary
        """
