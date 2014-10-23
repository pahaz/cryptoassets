"""

    Base classes for cryptocurrency backend.

"""


class Monitor:

    def include_new_address(self, address):
        """ Include a new address on the incoming transaction receiving list. """


class DummyMonitor(Monitor):
    """ An incoming transaction monitor which does nothing.
    """

    def start(self):
        pass

    def stop(self):
        pass