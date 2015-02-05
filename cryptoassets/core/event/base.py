import abc
import decimal
import json


class EventHandler(abc.ABC):
    """Post information about new receivent payments and transactions across processes.
    """

    @abc.abstractmethod
    def trigger(self, event_name, data):
        """Notify about a new event.

        :param event_name: Event name as a string

        :param data: Related data as dictionary
        """


def event_json_dumps(event_data):
    """Serializes the event as JSON.

    Decimals are converted to string, not float, to prevent the loss of accuracy.
    """

    def decimal_default(obj):
        if isinstance(obj, decimal.Decimal):
            return str(obj)
        raise TypeError

    return json.dumps(event_data, default=decimal_default)
