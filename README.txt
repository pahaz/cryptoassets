cryptoassets README
==================

Getting Started
---------------

- cd <directory containing this file>

- $VENV/bin/python setup.py develop

- $VENV/bin/initialize_cryptoassets_db development.ini

- $VENV/bin/pserve development.ini

Running tests
--------------

Example::

    export BLOCKIO_API_KEY="923f-e3e9-a580-dfb2"
    export BLOCKIO_PIN="foobar123"
    export BLOCKIO_TESTNET_TEST_FUND_ADDRESS="2MsgW3kCrRFtJuo9JNjkorWXaZSvLk4EWRr"
    python setup.py test


