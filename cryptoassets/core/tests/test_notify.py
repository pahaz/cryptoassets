"""Test posting notifications.

"""
import os
import stat
import unittest
import warnings

from .. import configure
from ..notify import notify

SAMPLE_SCRIPT_PATH = "/tmp/cryptoassets-test_notifier.sh"

SAMPLE_SCRIPT = """#/bin/sh

echo $2>> /tmp/cryptoassets-test_notifier
"""


class ShellNotificationTestCase(unittest.TestCase):
    """
    """

    def setUp(self):
        # ResourceWarning: unclosed <ssl.SSLSocket fd=9, family=AddressFamily.AF_INET, type=SocketType.SOCK_STREAM, proto=6, laddr=('192.168.1.4', 56386), raddr=('50.116.26.213', 443)>
        # http://stackoverflow.com/a/26620811/315168
        warnings.filterwarnings("ignore", category=ResourceWarning)  # noqa

        # Create a test script
        with io.iopen(SAMPLE_SCRIPT_PATH, "wt") as f:
            f.write(SAMPLE_SCRIPT)

        st = os.stat(SAMPLE_SCRIPT_PATH)
        os.chmod(SAMPLE_SCRIPT_PATH, st.st_mode | stat.S_IEXEC)

    def test_notify(self):
        """ Do a succesful notification test.
        """
        config = {
            "test_script": {
                "class": "cryptoassets.core.notify.shell.ShellNotifier",
                "script": SAMPLE_SCRIPT_PATH,
            }
        }
        configure.setup_notifier(config)

        notify.notify("foobar", {"test": "abc"})



