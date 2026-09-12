#!/bin/bash
set -euo pipefail
sudo systemctl disable --now pi-batt.service 2>/dev/null || true
sudo rm -f /etc/systemd/system/pi-batt.service /etc/xdg/autostart/pi-batt.desktop /usr/share/applications/pi-batt.desktop
sudo systemctl daemon-reload
sudo rm -f /usr/local/bin/pi-batt /usr/local/bin/pi-battctl
sudo rm -rf /opt/pi-batt
printf 'Keep Pi-Batt history/config? [Y/n] '
read -r ans
if [[ "$ans" =~ ^[Nn]$ ]]; then sudo rm -rf /var/lib/pi-batt /etc/pi-batt; fi
echo "Pi-Batt removed."
