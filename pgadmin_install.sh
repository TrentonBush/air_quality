#!/usr/bin/bash
# no arm64 support so can't use apt
# this is setup for the python library, installed via pip (not on conda)
sudo mkdir /var/lib/pgadmin
sudo mkdir /var/log/pgadmin
sudo chown ubuntu /var/lib/pgadmin
sudo chown ubuntu /var/log/pgadmin
# conda activate rpi
# pip install pgadmin4
# initially my install failed because I didn't have a g++ compiler. Installed that and everything worked