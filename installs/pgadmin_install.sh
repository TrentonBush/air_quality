#!/usr/bin/bash
# no arm64 support so can't use apt
# this is setup for the python library, installed via pip (not on conda)
sudo apt-get install -y g++ # needed for brotli dependency
sudo mkdir -p /var/lib/pgadmin
sudo mkdir -p /var/log/pgadmin
sudo chown $USER /var/lib/pgadmin
sudo chown $USER /var/log/pgadmin
pip install pgadmin4
