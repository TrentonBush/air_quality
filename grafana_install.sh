#!/usr/bin/bash
sudo apt-get install -y apt-transport-https
sudo apt-get install -y software-properties-common wget
wget -q -O - https://packages.grafana.com/gpg.key | sudo apt-key add -
echo "deb https://packages.grafana.com/oss/deb stable main" | sudo tee -a /etc/apt/sources.list.d/grafana.list
sudo apt-get update
sudo apt-get install grafana
# start it up
sudo systemctl daemon-reload
sudo systemctl start grafana-server
# enable start at boot
sudo systemctl enable grafana-server.service
echo "verify status: sudo systemctl status grafana-server"

echo "login to http://<your-ip>:3000/ to change user:pass from admin:admin"