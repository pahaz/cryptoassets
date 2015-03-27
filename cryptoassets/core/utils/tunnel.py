"""Expose local HTTP ports to the world using ngrok service.

Today many API services provide webhooks calling back your website or system over HTTP. This enables simple third party interprocess communications for websites. However unless you are running in production, you often find yourself in a situation where it is not possible to get an Internet exposed HTTP endpoint over publicly accessible IP address. These situations may include your home desktop, public WI-FI access point or continuous integration services. Thus, developing or testing against webhook APIs become painful for contemporary nomad developers.

`ngrok <https://ngrok.com/>`_ (`source <https://github.com/inconshreveable/ngrok>_`) is a pay-what-you-want service to create HTTP tunnels through third party relays. What makes ngrok attractice is that the registration is dead simple with Github credentials and upfront payments are not required. ngrok is also open source, so you can run your own relay for sensitive traffic.

In this blog post, I present a Python solution how to programmatically create ngrok tunnels on-demand. This is especially useful for webhook unit tests, as you have zero configuration tunnels available anywhere where you run your code. ngrok is spawned as a controlled subprocess for a given URL. Then, you can tell your webhook service provider to use this URL to make calls back to your unit tests.

One could use ngrok completely login free. In this case you lose the ability to name your HTTP endpoints. I have found it practical to have control over the endpoint URLs, as this makes debugging much more easier.

For real-life usage, you can check `cryptoassets.core project <https://pypi.python.org/pypi/cryptoassets.core>`_ where I came up with ngrok method. ngrok succesfully tunneled me out from `drone.io CI service <http://drone.io/>`_ and my laptop.

Installation
-------------

Installing ngrok on OSX from `Homebrew <http://brew.sh/>`_::

    brew install ngrok

Installing ngrok for Ubuntu::

    apt-get install -y unzip
    cd /tmp
    wget -O ngrok.zip "https://api.equinox.io/1/Applications/ap_pJSFC5wQYkAyI0FIVwKYs9h1hW/Updates/Asset/ngrok.zip?os=linux&arch=386&channel=stable"
    unzip ngrok
    mv ngrok /usr/local/bin

`Official ngrok download, self-contained zips <https://ngrok.com/>`_.

Sign up for the ngrok service and grab your auth token.

Export auth token as an environment variable in your shell, don't store it in version control system::

    export NGROK_AUTH_TOKEN=xxx

Ngrok tunnel code
-------------------

Below is Python 3 code for ``NgrokTunnel`` class. See `the full source code here <https://bitbucket.org/miohtama/cryptoassets/src/b0758d8cdf74e00d58b513b8e65b05f9f706160f/cryptoassets/core/utils/tunnel.py?at=feat-blockio-webhook>`_.

Example code
-------------

Here is a short pseudo example from cryptoassets.core block.io webhook handler unit tests. `See the full unit test code here <https://bitbucket.org/miohtama/cryptoassets/src/b0758d8cdf74e00d58b513b8e65b05f9f706160f/cryptoassets/core/tests/test_block_io.py?at=feat-blockio-webhook#cl-111>`_.::

    class BlockWebhookTestCase(CoinTestRoot, unittest.TestCase):

        def setUp(self):

            self.ngrok = None

            self.backend.walletnotify_config["class"] = "cryptoassets.core.backend.blockiowebhook.BlockIoWebhookNotifyHandler"

            # We need ngrok tunnel for webhook notifications
            auth_token = os.environ["NGROK_AUTH_TOKEN"]
            self.ngrok = NgrokTunnel(21211, auth_token)

            # Pass dynamically generated tunnel URL to backend config
            tunnel_url = self.ngrok.start()
            self.backend.walletnotify_config["url"] = tunnel_url
            self.backend.walletnotify_config["port"] = 21211

            # Start the web server
            self.incoming_transactions_runnable = self.backend.setup_incoming_transactions(self.app.conflict_resolver, self.app.event_handler_registry)

            self.incoming_transactions_runnable.start()

        def teardown(self):

            # Stop webserver
            incoming_transactions_runnable = getattr(self, "incoming_transactions_runnable", None)
            if incoming_transactions_runnable:
                incoming_transactions_runnable.stop()

            # Stop tunnelling
            if self.ngrok:
                self.ngrok.stop()
                self.ngrok = None

Other
-----

`Please see the unit tests <https://bitbucket.org/miohtama/cryptoassets/src/b0758d8cdf74e00d58b513b8e65b05f9f706160f/cryptoassets/core/tests/test_tunnel.py?at=feat-blockio-webhook>`_ for ``NgrokTunnel`` class itself.

"""

import os
import time
import uuid
import logging
import subprocess
from distutils.spawn import find_executable


logger = logging.getLogger(__name__)


class NgrokTunnel:

    def __init__(self, port, auth_token, subdomain_base="zoq-fot-pik"):
        """Initalize Ngrok tunnel.

        :param auth_token: Your auth token string you get after logging into ngrok.com

        :param port: int, localhost port forwarded through tunnel

        :parma subdomain_base: Each new tunnel gets a generated subdomain. This is the prefix used for a random string.
        """
        assert find_executable("ngrok"), "ngrok command must be installed, see https://ngrok.com/"
        self.port = port
        self.auth_token = auth_token
        self.subdomain = "{}-{}".format(subdomain_base, str(uuid.uuid4()))

    def start(self, ngrok_die_check_delay=0.5):
        """Starts the thread on the background and blocks until we get a tunnel URL.

        :return: the tunnel URL which is now publicly open for your localhost port
        """

        logger.debug("Starting ngrok tunnel %s for port %d", self.subdomain, self.port)

        self.ngrok = subprocess.Popen(["ngrok", "-authtoken={}".format(self.auth_token), "-log=stdout", "-subdomain={}".format(self.subdomain), str(self.port)], stdout=subprocess.DEVNULL)

        # See that we don't instantly die
        time.sleep(ngrok_die_check_delay)
        assert self.ngrok.poll() is None, "ngrok terminated abrutly"
        url = "https://{}.ngrok.com".format(self.subdomain)
        return url

    def stop(self):
        """Tell ngrok to tear down the tunnel.

        Stop the background tunneling process.
        """
        self.ngrok.terminate()
