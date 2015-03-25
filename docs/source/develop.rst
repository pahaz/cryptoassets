================================
Developing cryptoassets.core
================================

.. contents:: :local:


Running tests
--------------

Unit tests are `PyTest based <http://pytest.org/>`_.

Testing prerequisites
++++++++++++++++++++++

To run all tests several components must be in-place

* `pip install test-extra-requirements.txt``

* Check block.io credentials in tests/config.yaml files (hardcoded accounts, testnet coins)

* *bitcoind* running testnet on localhost, configured for named UNIX pipe wallet notifications (see config snipped below). bitcoind must have account *cryptoassets* with enough balance to do withdraw tests.

* PostgreSQL database ``unittest-conflict-resolution`` where you can connect on localhost without username and password

* Redis installed, with preferable empty database 0

* `ngrok account <http://ngrok.com>`_ is required for running block.io webhook tests. You need to create ``~/.ngrok`` file with your auth token::

    ngrok -authtoken xxx 80

Examples for running tests
+++++++++++++++++++++++++++

Running all tests::

    py.test cryptoassets

Running a single test case::

    py.test cryptoassets/core/tests/test_conflictresolver.py

Running a single test::

    py.test -k "BitcoindTestCase.test_send_internal" cryptoassets

Running a single test with verbose Python logging output to stdout (useful for pinning down *why* the test fails)::

    VERBOSE_TEST=1 py.test -k "BitcoindTestCase.test_send_internal" cryptoassets

Running tests for continuous integration service (15 minute timeout) and skipping slow tests where transactions are routed through cryptocurrency network (full BTC send/receive test, etc.)::

    CI=true py.test cryptoassets

Running unittests using vanilla Python 3 unittest::

    python -m unittest discover

(This ignores all skipping hints)

More info

* http://pytest.org/latest/usage.html

Bitcoind testnet
------------------

Setting up TESTNET bitcoind on OSX
++++++++++++++++++++++++++++++++++++

Edit ``/Users/mikko/Library/Application Support/Bitcoin/bitcoin.conf``::

    testnet=1
    server=1
    rpcuser=foo
    rpcpassword=bar
    rpctimeout=5
    rpcport=8332
    txindex=1
    rpcthreads=64
    walletnotify=gtimeout --kill-after=10 5 /bin/bash -c "echo %s >> /tmp/cryptoassets-unittest-walletnotify-pipe

Restart **Bitcoin-Qt**. Now it should give green icon instead of standard orange.

Test the JSON-RPC server connection::

     curl --user foo:bar --data-binary '{"id":"t0", "method": "getinfo", "params": [] }' http://127.0.0.1:8332/

http://suffix.be/blog/getting-started-bitcoin-testnet

Starting bitcoind in debug mode::

    /Applications/Bitcoin-Qt.app/Contents/MacOS/Bitcoin-Qt -printtoconsole -debug

Building bitcoind on Ubuntu
++++++++++++++++++++++++++++++

* http://bitzuma.com/posts/compile-bitcoin-core-from-source-on-ubuntu/

Topping up bitcoind
++++++++++++++++++++++

First create a receiving address under ``bitcoind`` accounting account ``cryptoassets``::

    curl --user foo:bar --data-binary '{"id":"t0", "method": "getnewaddress", "params": ["cryptoassets"] }' http://127.0.0.1:8332/

Write down the *result*.


Testnet faucet
++++++++++++++++

Get Testnet coins from here:

http://tpfaucet.appspot.com/

(`Alternative testnet faucets <http://bitcoin.stackexchange.com/questions/17690/is-there-any-where-to-get-free-testnet-bitcoins>`_.)

Send them to the receiving address you created.

Then list ``bitcoind`` accounts and balances, to see you have the new receiving address and the balance arrives there:

    curl --user foo:bar --data-binary '{"id":"t0", "method": "listaccounts", "params": [] }' http://127.0.0.1:8332/

Dumping your TESTNET private address for importing in tests
++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

Example using public address ``mk2o9anFwtHFGFKeD89Qxh5YBhNMQk7NrS``::

    curl --user foo:bar --data-binary '{"id":"t0", "method": "dumpprivkey", "params": ["mk2o9anFwtHFGFKeD89Qxh5YBhNMQk7NrS"] }' http://127.0.0.1:8332/

Using bitcoind with multiple backends
++++++++++++++++++++++++++++++++++++++

If you are using same bitcoind testnet instance to drive several cryptoassets backends, you can multiplex incoming transactions to several wallet notify pipes with a shell script like::

    #!/bin/bash
    echo "Got txid $1" >> /tmp/txlist.txt
    # Timeout is needed to work around for hanging named pipe cases where Bitcoin-QT process starts to write to a named pipe, but nobody is reading it, thus preventing clean shutdown of the parent process (bitcoind)
    gtimeout --kill-after=10 5 /bin/bash -c "echo $1 >> /tmp/cryptoassets-unittest-walletnotify-pipe"
    gtimeout --kill-after=10 5 /bin/bash -c "echo $1 >> /tmp/tatianastore-cryptoassets-helper-walletnotify"
    exit 0

Also needs coreutils on OSX::

    brew install coreutils

Conflicted transactions
++++++++++++++++++++++++++++++++++++++

If Bitcoin-QT starts to display transactions sent via RPC as **conflicted** status

1) Your walletnotifty script might be broken, CTRL+C abort Bitcoin-QT in terminal, check error messages::

    /Users/mikko/code/notify.sh: line 3: timeout: command not found
    runCommand error: system(/Users/mikko/code/notify.sh 94506c797452745b87e734caf35ec4b62c0ef61f6c7efa5869f22ec0f1a71abf) returned 32512

2) rescan blockchain (unclean shutdown?)::

    /Applications/Bitcoin-Qt.app/Contents/MacOS/Bitcoin-Qt -printtoconsole -debug -rescan

3) Make sure "Spend unconfirmed outputs" is toggled off in Bitcoin-QT preferences

4) Make sure you are displaying correct transactions and not old ones (Bitcoin QT pops old conflicting transactions at the top of the history list). Choose "Today" from Bitcoin QT transaction list filters.

Continuous integration
-----------------------

Continuous integration is running on drone.io <https://drone.io/bitbucket.org/miohtama/cryptoassets/>`_.

See ``tests/setup-testing-droneio.sh`` how tests are executed.

Full CI test suite
+++++++++++++++++++

Because some tests may take more than 15 minutes to execute, full test suite cannot be run on CI environment. There is script ``full-run-tests.sh`` which can be used to run tests on Linux VM + bitcoind testnet instance.

Run this script on a server having running Bitcoind instance.

Releases
----------



