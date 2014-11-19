"""Run a script on a notification.
"""
import logging
import json
import subprocess
import os

from .base import Notifier

logger = logging.getLogger(__name__)


class ScriptNotificationFailed(Exception):
    """Script executed for the notification returned non-zero exit code."""


class ScriptNotifier(Notifier):
    """Execute an UNIX command on a new event.

    Blocks the execution until the executed command returns.

    The following environment variables are set for the script::

        CRYPTOASSETS_EVENT_NAME="event name as a string"
        CRYPTOASSETS_EVENT_DATA="JSON encoded data"

    If the executed command returns non-zero status, this notification handler raises ``ShellNotificationFailed``.
    """

    def __init__(self, script, log_output=False):
        """
        :param script: Executed shell command

        :param log_output: If true send the output from the executed command to cryptoassets logs on INFO log level
        """
        self.script = script
        self.log_output = log_output

    def trigger(self, event_name, data):
        assert type(event_name) == str
        data = json.dumps(data)
        args = (self.script,)

        env = os.environ.copy()
        env["CRYPTOASSETS_EVENT_NAME"] = event_name
        env["CRYPTOASSETS_EVENT_DATA"] = data

        p = subprocess.Popen(args, shell=True, env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE)
        stdout, stderr = p.communicate()

        if self.log_output:
            logger.info("Executed notification script %s, exit code %d", args, p.returncode)
            logger.info("stdout: %s", stdout)
            logger.info("stderr: %s", stderr)

        if p.returncode != 0:
            raise ScriptNotificationFailed("Executing notification script {} got exit value {}".format(args, p.returncode))
