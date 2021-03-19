sensors_install:
	pip install -e .

user_i2c_permissions:
	sudo groupadd i2c
	sudo chown :i2c /dev/i2c-1
	sudo chmod 660 /dev/i2c-1
	sudo usermod -aG i2c $USER
	echo 'KERNEL=="i2c-[0-9]*", GROUP="i2c"' | sudo tee -a /etc/udev/rules.d/10-local_i2c_group.rules

grafana_install:
	sudo apt-get install -y apt-transport-https
	sudo apt-get install -y software-properties-common wget
	wget -q -O - https://packages.grafana.com/gpg.key | sudo apt-key add -
	echo "deb https://packages.grafana.com/oss/deb stable main" | sudo tee -a /etc/apt/sources.list.d/grafana.list
	sudo apt-get update
	sudo apt-get install -y grafana
	# start it up
	sudo systemctl daemon-reload
	sudo systemctl start grafana-server
	# enable start at boot
	sudo systemctl enable grafana-server.service
	echo "login to http://<your-ip>:3000/ to change user:pass from admin:admin"

timescaledb_install:
	# timescaledb does not have apt packages built for aarch64/arm64.
	# Their instructions for building from source were not quite complete.
	# Here was my process, cobbled together from various github issues and trial and error:

	sudo apt install -y postgresql-12 postgresql-server-dev-12 libkrb5-dev libssl-dev

	git clone https://github.com/timescale/timescaledb.git timescaledb
	cd timescaledb
	git checkout 2.0.0

	./bootstrap -DREGRESS_CHECKS=OFF -DWARNINGS_AS_ERRORS=OFF
	cd ./build && make  
	sudo make install

	# uncomment the line matching that string
	sudo sed -i "/shared_preload_libraries = 'timescaledb'/s/^#//g" /etc/postgresql/12/main/postgresql.conf"
	# if install fails here because path doesn't exist, find it with:
	# sudo -i -u postgres
	# psql -d postgres -c "SHOW config_file;"
	sudo systemctl restart postgresql.service

database_setup: timescaledb_install
	psql -h localhost -p 5432 -U postgres -a -f ./sql/admin.sql
	psql -h localhost -p 5432 -U postgres -d air_quality -a -f ./sql/db_setup.sql

data_logger_service_install: database_setup sensors_install user_i2c_permissions
	# systemd service to run on boot as current user (instead of root)
	# https://stackoverflow.com/questions/53928299/how-to-convert-a-python-script-in-a-local-conda-env-into-systemd-service-in-linu
	mkdir -p ~/.config/systemd/user/
	cp ./data_logger.service ~/.config/systemd/user/
	# enable user services on boot
	loginctl enable-linger $USER
	# start it up
	systemctl --user enable data_logger.service
	systemctl --user start data_logger.service

install: grafana_install data_logger_service_install


# optional
pgadmin_install:
	# no arm64 support so can't use apt
	# rather than build from source I turned to their python library
	# g++ needed for brotli dependency
	sudo apt-get install -y g++
	sudo mkdir -p /var/lib/pgadmin
	sudo mkdir -p /var/log/pgadmin
	sudo chown $USER /var/lib/pgadmin
	sudo chown $USER /var/log/pgadmin
	pip install pgadmin4
