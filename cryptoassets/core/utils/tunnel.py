"""Expose local HTTP ports to the world using localtunnel utility.

Open a background thread doing HTTP tunnel using `ngrok service <https://ngrok.com/>`_.

Installing ngrok on OSX::

    brew install ngrok

Installing ngrok on Ubutunu::

    TODO

You need to have signed up for the ngrok service and created ~/.ngrok configuration file::

    ngrok -authtoken xxx 80

"""

import os
import time
import uuid
import logging
import subprocess
from distutils.spawn import find_executable


logger = logging.getLogger(__name__)


class NgrokTunnel:

    def __init__(self, port, subdomain_base="zoqfotpik"):
        assert find_executable("ngrok"), "ngrok command must be installed, see https://ngrok.com/"
        self.port = port
        self.subdomain = subdomain_base + str(uuid.uuid4())

    def start(self, ngrok_die_check_delay=0.5):
        """Starts the thread on the background and blocks until we get a tunnel URL."""

        logger.debug("Starting ngrok tunnel %s for port %d", self.subdomain, self.port)

        # XXX: Windows, oops
        self.ngrok = subprocess.Popen(["ngrok", "-log=stdout", "-subdomain={}".format(self.subdomain), str(self.port)], stdout=subprocess.DEVNULL)

        # See that we don't instantly die
        time.sleep(ngrok_die_check_delay)
        assert self.ngrok.poll() is None, "ngrok terminated abrutly"
        url = "https://{}.ngrok.com".format(self.subdomain)
        return url

    def stop(self):
        self.ngrok.terminate()
