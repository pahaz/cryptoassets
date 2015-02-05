#!/bin/bash
#
# Run all tests, including slow ones, on pre-setup Linux box.
#
# Send out coverage report to coveralls
#
#

set -e

# Read secrets file on the server
source "$HOME/test-env"

CHECKOUT_HOME=`pwd`

# Build SSH tunnelling to the bitcoind server
# First grab SSH key from drone.io config so it's not visible in build log
echo $SSH_PRIV_KEY | tr "," "\n" > /tmp/private-key
chmod o-wrx,g-rwx /tmp/private-key
ssh -q -N -F $CHECKOUT_HOME/cryptoassets/core/tests/droneio-ssh-config tunnel@$BITCOIND_SERVER &
SSH_PID=$!

# Run tests using py.test test runner
echo "Running tests"
# http://stackoverflow.com/a/13496073/315168
py.test-3.4 -rsx --timeout=3600 --durations=10 --cov cryptoassets  --cov-report xml cryptoassets
echo "Done with tests"

# Shutdown SSH tunnel
echo "Shutting down SSH tunnel pid $SSH_PID"
# ssh -S ssh-ctrl-socket -O exit
kill $SSH_PID

# Update data to codecov.io
codecov --token="$CODECOV_TOKEN"



