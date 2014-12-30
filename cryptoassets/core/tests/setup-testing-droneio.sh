#!/bin/bash
#
# Setup test running for Ubuntu 12.02 / Drone IO
#

set -e

CHECKOUT_HOME=/home/ubuntu/src/bitbucket.org/miohtama/cryptoassets

# Need to upgrade to Python 3.4
sudo add-apt-repository ppa:fkrull/deadsnakes 2>&1 > /dev/null
sudo apt-get -qq update 2>&1 > /dev/null
sudo apt-get -qq install python3.4-dev 2>&1 > /dev/null

python3.4 -m venv venv
. venv/bin/activate

# Make sure pip itself is up to date
pip install -U --quiet pip
pip install --quiet -r requirements.txt --use-mirrors
pip install --quiet -r test-extra-requirements.txt --use-mirrors

# Make sure we have PSQL test database for conflict resolver test case
# http://docs.drone.io/databases.html
psql -c 'CREATE DATABASE IF NOT EXISTS "unittest-conflict-resolution";' -U postgres

# Build SSH tunnelling to the bitcoind server
# First grab SSH key from drone.io config so it's not visible in build log
echo "" > /tmp/private-key
for i in $(echo $SSH_PRIV_KEY | tr "," "\n")
do
    echo $i >> /tmp/private-key
done
chmod o-wrx,g-rwx /tmp/private-key
ssh -vvv -N -f -F $CHECKOUT_HOME/cryptoassets/core/tests/droneio-ssh-config $BITCOIND_SERVER

# Run tests using py.test test runner
ls venv/bin  # debug
venv/bin/py.test-3.4 cryptoassets


