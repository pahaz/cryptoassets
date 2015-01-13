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

# Run tests using py.test test runner
echo "Running tests"
# http://stackoverflow.com/a/13496073/315168
py.test-3.4 -rsx --timeout=3600 --durations=10 --cov cryptoassets  --cov-report xml cryptoassets
echo "Done with tests"

# Update data to codecov.io
codecov --token="$CODECOV_TOKEN"


