"""Shell and executable runner notifiers.
"""
import json
import subprocess

from .base import Notifier


class ShellNotificationFailed(Exception):
    pass


class ShellNotifier(Notifier):
    """Execute a shell command on new event.

    Blocks the execution until the executed command returns.

    Gives the following arguments to the *script*:

        event event-data-as-json

    If the executed command returns non-zero status, log as exception.
    """

    def __init__(self, script):
        """
        :param script: Executed shell command
        """
        self.script = script

    def trigger(self, event_name, data):
        assert type(event_name) == str
        data = json.dumps(data)
        args = [event_name, data]
        exit_val = subprocess.call(self.script, args, shell=True)
        if exit_val != 0:
            raise ShellNotificationFailed("Executing shell notification command {} with arguments {} got exit value {}".format(self.script, args, exit_val))
