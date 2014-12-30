================================
Installation
================================

.. contents:: :local:

Installing cryptoassets.core package
======================================

Requirements
-------------

You need at least Python version 3.4.

* Ubuntu 14.04 comes with Python 3.4. `Install Python 3.4 on older versions of Ubuntu <http://askubuntu.com/q/449555/24746>`_

* `Install Python 3.4 on OSX <https://www.python.org/downloads/mac-osx/>`_

* Microsoft Windows is untested, but should work

Older Python versions might work, but are untested.

Ubuntu / Debian and Python 3.4 virtualenv and pip issue
+++++++++++++++++++++++++++++++++++++++++++++++++++++++++

.. note ::

    Ubuntu and Debian have an open issue regarding Python 3.4 virtualenv support. Thus, check the link below for how to workaround installation issues if you are using a non-conforming distribution.

* `Issues with Ubuntu / Debian, Python 3.4 and virtualenv <https://lists.debian.org/debian-python/2014/03/msg00045.html>`_ - `see workaround <https://bugs.launchpad.net/ubuntu/+source/python3.4/+bug/1290847/comments/58>`_

Create a virtualenv
---------------------

``cryptoassets.core`` is distributed as a Python package. Follow the Python community best practices and `create a virtualenv <https://packaging.python.org/en/latest/installing.html#virtual-environments>`_ where you to install the package and its dependencies.

OSX::

    mkdir myproject
    cd myproject
    python3.4 -m venv venv
    source venv/bin/activate

Installing cryptoassets package
---------------------------------

Installing the release version
++++++++++++++++++++++++++++++++++++

After virtualenv is created and active you can run::

    # Install the known good versions of dependencies
    curl "https://bitbucket.org/miohtama/cryptoassets/raw/bdb2e36b63ce751aef1bbdec169a55536f80692b/requirements.txt" > requirements.txt && pip install -r requirements.txt

    # Install the latest version of cryptoassets.core package
    pip install cryptoassets.core

This will use the latest package pindowns of known good version set.

Installing the development version
++++++++++++++++++++++++++++++++++++

First install dependencies.

Checkout and install from Bitbucket::

    git clone https://miohtama@bitbucket.org/miohtama/cryptoassets.git
    cd cryptoassets
    python setup.py develop



