================================
Developing cryptoassets.core
================================

.. contents:: :local:


Running tests
--------------

Example::

    # Testnet API keys
    export BLOCK_IO_API_KEY="923f-e3e9-a580-dfb2"
    export BLOCK_IO_API_KEY_DOGE="0266-c2b6-c2c8-ee07"
    export BLOCK_IO_PIN="foobar123"
    export BLOCK_IO_TESTNET_TEST_FUND_ADDRESS="2MsgW3kCrRFtJuo9JNjkorWXaZSvLk4EWRr"
    export BLOCK_IO_DOGE_TESTNET_TEST_FUND_ADDRESS="2MxkkbbAwjT7pXme5766d6LUmKyZYEpDTMi"

    # block.io receiving transaction testing
    export PUSHER_API_KEY="e9f5cc20074501ca7395"

    # bitcoind TESTNET credenditals
    export BITCOIND_URL="http://foo:bar@127.0.0.1:8332/"
    # import this private address where we have some TESTNET balance
    # this is private key:address tuple
    export BITCOIND_TESTNET_FUND_ADDRESS="cRV3TMMPaeGomwwNt76i2Dz2DghAaVmjdRyeHDWcup71pKe2jpcF:mxd636hBuxiuJavfWjQ3Aw6EiZQr5MtFZi"

    # A real wallet, not testnet!
    export BLOCKCHAIN_IDENTIFIER="x"
    export BLOCKCHAIN_PASSWORD="y"

Running all tests::

    python setup.py test

Running a single test::

    python -m unittest cryptoassets.core.tests.test_block_io.BlockIoBTCTestCase.test_send_receive_external

Running a single test with more verbose logging output:

    VERBOSE_TEST=1 python -m unittest cryptoassets.core.tests.test_block_io.BlockIoBTCTestCase.test_charge_network_fee

Bitcoind testnet
------------------

Setting up TESTNET bitcoind on OSX
++++++++++++++++++++++++++++++++++++

Edit ``/Users/mikko/Library/Application Support/Bitcoin/bitcoin.conf``::

    testnet=1
    server=1
    rpcuser=foo
    rpcpassword=bar
    rpctimeout=30
    rpcport=8332
    txindex=1

Restart **Bitcoin-Qt**. Now it should give green icon instead of standard orange.

Test the JSON-RPC server connection::

     curl --user foo:bar --data-binary '{"id":"t0", "method": "getinfo", "params": [] }' http://127.0.0.1:8332/

http://suffix.be/blog/getting-started-bitcoin-testnet

Starting bitcoind in debug mode::

    /Applications/Bitcoin-Qt.app/Contents/MacOS/Bitcoin-Qt -printtoconsole -debug

Topping up bitcoind
++++++++++++++++++++++

First create a receiving address under ``bitcoind`` accounting account ``cryptoassets``::

    curl --user foo:bar --data-binary '{"id":"t0", "method": "getnewaddress", "params": ["cryptoassets"] }' http://127.0.0.1:8332/

Then list ``bitcoind`` accounts and balances:

    curl --user foo:bar --data-binary '{"id":"t0", "method": "listaccounts", "params": [] }' http://127.0.0.1:8332/


TESTNET faucet
++++++++++++++++

Get TESTNET coins from here:

http://tpfaucet.appspot.com/

Send them to the address you created.

Dumping your TESTNET private address for importing in tests
++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

Example using public address ``mk2o9anFwtHFGFKeD89Qxh5YBhNMQk7NrS``::

    curl --user foo:bar --data-binary '{"id":"t0", "method": "dumpprivkey", "params": ["mk2o9anFwtHFGFKeD89Qxh5YBhNMQk7NrS"] }' http://127.0.0.1:8332/

Continuous integration
-----------------------

Continuous integration is running on drone.io <https://drone.io/bitbucket.org/miohtama/cryptoassets/>`_.

The recipe to run the tests on Python 3.4::


