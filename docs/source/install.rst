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

* Microsoft Windows is unsupported at the moment as the authors do not have access to Microsoft Windows development tools

Create a virtualenv
---------------------

``cryptoassets.core`` is distributed as a Python package. To use packages in your application, follow the Python community best practices and `create a virtualenv <https://packaging.python.org/en/latest/installing.html#virtual-environments>`_ where you to install the third party packages and their dependencies.

OSX
++++

For Homebrew with Python 3.4 installed::

    mkdir myproject
    cd myproject
    virtualenv python3.4 -m venv venv
    source venv/bin/activate

Ubuntu / Debian
+++++++++++++++++++

First get a virtualenv which is not old and horribly broken, like the one in the system default installation::

    sudo pip install -U virtualenv

This creates ``/usr/local/bin/virtualenv``. Then::

    mkdir myproject
    cd myproject
    virtualenv -p python3.4 venv
    source venv/bin/activate

.. note ::

    Ubuntu and Debian have an open issue regarding Python 3.4 virtualenv support. Thus, check the link below for how to workaround installation issues if you are using a non-conforming distribution.

* `Issues with Ubuntu / Debian, Python 3.4 and virtualenv <https://lists.debian.org/debian-python/2014/03/msg00045.html>`_ - `see workaround <https://bugs.launchpad.net/ubuntu/+source/python3.4/+bug/1290847/comments/58>`_

Installing cryptoassets package
---------------------------------

Installing the release version
++++++++++++++++++++++++++++++++++++

After virtualenv is created and active you can run::

    # Install the known good versions of dependencies
    curl -o requirements.txt "https://bitbucket.org/miohtama/cryptoassets/raw/9bfbe5e16fd878cbb8231f06d8825e1e1af94495/requirements.txt" && pip install -r requirements.txt

    # Install the latest release version of cryptoassets.core package
    pip install cryptoassets.core

This will use the latest package pindowns of known good version set.

Installing the development version
++++++++++++++++++++++++++++++++++++

You can install git checkout if you want to develop / bug fix *cryptoassets.core* itself.

First install dependencies.

Checkout and install from Bitbucket::

    git clone https://miohtama@bitbucket.org/miohtama/cryptoassets.git
    cd cryptoassets
    python setup.py develop



