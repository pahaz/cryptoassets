#!/bin/sh
#
# Setup test running for Ubuntu 12.02 / Drone IO
#

CHECKOUT_HOME=/home/ubuntu/src/bitbucket.org/miohtama/cryptoassets

# Need to upgrade to Python 3.4
sudo add-apt-repository ppa:fkrull/deadsnakes 2>&1 > /dev/null
sudo apt-get -qq update; sudo apt-get -qq install python3.4-dev

python3.4 -m venv venv
source venv/bin/activate

# Make sure pip itself is up to date
pip install -U --quiet pip
pip install --quiet -r requirements.txt --use-mirrors
pip install --quiet -r test-extra-requirements.txt --use-mirrors

# Make sure we have PSQL test database for conflict resolver test case
# http://docs.drone.io/databases.html
psql -c 'create database "unittest-conflict-resolution";' -U postgres

# Build SSH tunnelling to the bitcoind server
# First grab SSH key from drone.io config so it's not visible in build log
echo "" > /tmp/private-key
for i in $(echo $SSH_PRIV_KEY | tr "," "\n")
do
    echo $i >> /tmp/private-key
done
chmod o-wrx,g-rwx /tmp/private-key
eval `ssh-agent`
ssh-add /tmp/private-key
ssh -f -F $CHECKOUT_HOME/cryptoassets/core/tests/droneio-ssh-config bitcoind-test-server

# Run tests using py.test test runner
py.test cryptoassets


