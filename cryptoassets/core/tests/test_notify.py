"""Test posting notifications.

"""
import io
import os
import stat
import unittest
import warnings
import json

from .. import configure
from ..notify import notify

SAMPLE_SCRIPT_PATH = "/tmp/cryptoassets-test_notifier.sh"

SAMPLE_SCRIPT = """#/bin/sh
echo Foo
echo $0
echo $CRYPTOASSETS_EVENT_NAME
echo $CRYPTOASSETS_EVENT_DATA

echo $CRYPTOASSETS_EVENT_DATA > /tmp/cryptoassets-test_notifier
"""


class ScriptNotificationTestCase(unittest.TestCase):
    """
    """

    def setUp(self):
        # ResourceWarning: unclosed <ssl.SSLSocket fd=9, family=AddressFamily.AF_INET, type=SocketType.SOCK_STREAM, proto=6, laddr=('192.168.1.4', 56386), raddr=('50.116.26.213', 443)>
        # http://stackoverflow.com/a/26620811/315168
        warnings.filterwarnings("ignore", category=ResourceWarning)  # noqa

        # Create a test script
        with io.open(SAMPLE_SCRIPT_PATH, "wt") as f:
            f.write(SAMPLE_SCRIPT)

        st = os.stat(SAMPLE_SCRIPT_PATH)
        os.chmod(SAMPLE_SCRIPT_PATH, st.st_mode | stat.S_IEXEC)

    def test_notify(self):
        """ Do a succesful notification test.
        """
        config = {
            "test_script": {
                "class": "cryptoassets.core.notify.script.ScriptNotifier",
                "script": SAMPLE_SCRIPT_PATH,
                "log_output": True
            }
        }
        configure.setup_notify(config)

        notify("foobar", {"test": "abc"})

        with io.open("/tmp/cryptoassets-test_notifier", "rt") as f:
            data = json.load(f)
            self.assertEqual(data["test"], "abc")

