#!/usr/bin/bash
# systemd service to run on boot as current user (instead of root)
# https://stackoverflow.com/questions/53928299/how-to-convert-a-python-script-in-a-local-conda-env-into-systemd-service-in-linu
mkdir -p ~/.config/systemd/user/
cp ../data_logger.service ~/.config/systemd/user/
loginctl enable-linger $USER # enable user services on boot
systemctl --user enable data_logger.service
systemctl --user start data_logger.service
