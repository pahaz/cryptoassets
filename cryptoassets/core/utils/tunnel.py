"""Expose local HTTP ports to the world using localtunnel utility.

Many API services provide webhooks which call back your service or website over HTTP, as this enables simple integration with websites. However unless you are running in production, you often  find yourself in a situation where it is not possible to get an Internet exposed HTTP endpoint over publicly accessible IP address. These situations include your home desktop, public WI-FI access point and continuous integration services. Thus, developing or testing against webhook APIs become painful for contemporary nomad developers.

`ngrok <https://ngrok.com/>`_ is a free (pay-what-you-want) service to automatically generate HTTP tunnels through the third party relay. What makes ngrok attractice is that the registration is dead simple with your Github credentials and upfront payments are not required.

In this blog post, I present a Python solution how to programmatically create ngrok tunnels on-demand. This is especially useful for webhook unit tests, as you can zero configuration tunnels available anywhere where you run your code. ngrok is spawned as a controlled subprocess for a given URL. Then, you can tell your webhook service provider to use this URL to make calls back to your unit tests.

One could use ngrok completely login free. In this case you lose the ability to name your HTTP endpoints. I have found it practical to have control over your HTTP endpoint URLs, as this makes debugging much more easier.

For real-life usage, you can always check `cryptoassets.core project <https://pypi.python.org/pypi/cryptoassets.core>`_ where I came up with this method.

Installation
-------------

Installing ngrok on OSX from `Homebrew <http://brew.sh/>`_::

    brew install ngrok

`Deb package for installing ngrok on Ubuntu <http://packages.ubuntu.com/trusty/web/ngrok-client>`_.

`Official ngrok download (self-contained zip) <https://ngrok.com/>`_.

Sign up for the ngrok service and grab your auth token.

Export auth token as an environment variable in your shell, don't store it in version control system::

    export NGROK_AUTH_TOKEN=xxx

Ngrok tunnel code
-------------------

See the full code here.

Usage
------

Here is a short usage example from cryptoassets.core block.io webhook handler unit tests. See the full code here.

Other
-----

Please see the unit tests for ``NgrokTunnel``class itself.

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

        :parma subdomain_base: Each tunnel gets a new generated subdomain. This is the prefix used in a random string.
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
