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

    export BLOCK_IO_API_KEY="923f-e3e9-a580-dfb2"
    export BLOCK_IO_API_KEY_DOGE="0266-c2b6-c2c8-ee07"
    export BLOCK_IO_PIN="foobar123"
    export BLOCK_IO_TESTNET_TEST_FUND_ADDRESS="2MsgW3kCrRFtJuo9JNjkorWXaZSvLk4EWRr"
    export BLOCK_IO_DOGE_TESTNET_TEST_FUND_ADDRESS="2MxkkbbAwjT7pXme5766d6LUmKyZYEpDTMi"


    # A real wallet, not testnet!
    export BLOCKCHAIN_IDENTIFIER="x"
    export BLOCKCHAIN_PASSWORD="y"


    python setup.py test



