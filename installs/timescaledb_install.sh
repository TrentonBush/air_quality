#!/usr/bin/bash
# timescaledb does not have apt packages built for aarch64/arm64.
# Their instructions for building from source were not quite complete.
# Here was my process, cobbled together from various github issues and trial and error:

sudo apt install postgresql-12 postgresql-server-dev-12 libkrb5-dev libssl-dev

git clone https://github.com/timescale/timescaledb.git timescaledb
cd timescaledb
git checkout 2.0.0

./bootstrap -DREGRESS_CHECKS=OFF -DWARNINGS_AS_ERRORS=OFF
cd ./build && make  
sudo make install

sudo -i -u postgres
psql -d postgres -c "SHOW config_file;"
echo "NOT DONE! In the above config file, uncomment the line: shared_preload_libraries = 'timescaledb'"
# it was: /etc/postgresql/12/main/postgresql.conf
echo "example: sudo nano /etc/postgresql/12/main/postgresql.conf"
echo "then restart postgres: sudo systemctl restart postgresql.service"
