#!/bin/bash
#
# Setup test running for Ubuntu 12.02 / Drone IO
#
#
# To create authorized key on the server:
# sudo -i -u tunnel
# ssh-keygen
# echo -n 'command="echo port forwarding only",no-pty,permitopen="localhost:8332" '> .ssh/authorized_keys
# cat .ssh/id_rsa.pub >> .ssh/authorized_keys

set -e

CHECKOUT_HOME=/home/ubuntu/src/bitbucket.org/miohtama/cryptoassets

# Build SSH tunnelling to the bitcoind server
# First grab SSH key from drone.io config so it's not visible in build log
echo $SSH_PRIV_KEY | tr "," "\n" > /tmp/private-key
chmod o-wrx,g-rwx /tmp/private-key
ssh -N -f -F $CHECKOUT_HOME/cryptoassets/core/tests/droneio-ssh-config tunnel@$BITCOIND_SERVER
SSH_PID=$!

# Need to upgrade to Python 3.4
sudo add-apt-repository ppa:fkrull/deadsnakes > /dev/null 2>&1
sudo apt-get -qq update > /dev/null 2>&1
sudo apt-get -qq install python3.4-dev > /dev/null 2>&1

python3.4 -m venv venv
. venv/bin/activate

# Make sure pip itself is up to date
pip install -U --quiet pip
pip install --quiet -r requirements.txt --use-mirrors
pip install --quiet -r test-extra-requirements.txt --use-mirrors

# Make sure we have PSQL test database for conflict resolver test case
# http://docs.drone.io/databases.html
# no IF NOT EXISTS for psql
set +e
psql -c 'CREATE DATABASE "unittest-conflict-resolution";' -U postgres
set -e

# Run tests using py.test test runner
ls venv/bin  # debug
venv/bin/py.test-3.4 cryptoassets

# Shutdown SSH tunnel
kill $SSH_PID