#!/bin/bash
set -euo pipefail

if [[ $EUID -eq 0 ]]; then
  echo "Run this as your normal desktop user, NOT with sudo: ./install.sh"
  exit 1
fi

USER_NAME="$USER"
USER_GROUP="$(id -gn)"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

cd "$SCRIPT_DIR"

echo "== Pi-Batt v$(cat VERSION) installer =="
echo "Installing dependencies..."
sudo apt update
sudo apt install -y python3-smbus python3-pyqt5 i2c-tools sqlite3 libnotify-bin ca-certificates

echo "Preparing Pi-Batt directories..."
sudo mkdir -p /opt/pi-batt /etc/pi-batt /var/lib/pi-batt /run/pi-batt /usr/share/applications /etc/xdg/autostart

# Migrate the previous PiUPS installation if present.
if [[ -f /etc/piups/config.json && ! -f /etc/pi-batt/config.json ]]; then
  echo "Migrating PiUPS configuration..."
  sudo cp /etc/piups/config.json /etc/pi-batt/config.json
fi
if [[ -f /var/lib/piups/history.db && ! -f /var/lib/pi-batt/history.db ]]; then
  echo "Migrating PiUPS telemetry/history..."
  sudo cp /var/lib/piups/history.db /var/lib/pi-batt/history.db
fi

if systemctl list-unit-files piups.service >/dev/null 2>&1; then
  echo "Disabling old PiUPS service..."
  sudo systemctl disable --now piups.service 2>/dev/null || true
fi

echo "Installing application..."
sudo cp daemon.py gui.py pibatt_hw.py pibattctl.py updater.py VERSION manifest.json /opt/pi-batt/
sudo chmod 755 /opt/pi-batt/*.py
sudo chmod 644 /opt/pi-batt/VERSION /opt/pi-batt/manifest.json
sudo install -m 755 pi-batt-launch /usr/local/bin/pi-batt
sudo ln -sfn /opt/pi-batt/pibattctl.py /usr/local/bin/pi-battctl

if [[ ! -f /etc/pi-batt/config.json ]]; then
  sudo cp config.json /etc/pi-batt/config.json
else
  # Add new defaults without overwriting existing user settings.
  sudo python3 - "$SCRIPT_DIR/config.json" <<'PY'
import json, sys
from pathlib import Path
src=Path(sys.argv[1]); dst=Path('/etc/pi-batt/config.json')
defaults=json.loads(src.read_text())
try: current=json.loads(dst.read_text())
except Exception: current={}
merged=dict(defaults); merged.update(current)
dst.write_text(json.dumps(merged,indent=2)+'\n')
PY
fi

# Let the installing desktop user manage settings and create narrow update requests.
sudo chown root:"$USER_GROUP" /etc/pi-batt /etc/pi-batt/config.json /var/lib/pi-batt /run/pi-batt
sudo chmod 775 /etc/pi-batt /var/lib/pi-batt /run/pi-batt
sudo chmod 664 /etc/pi-batt/config.json
if [[ -f /var/lib/pi-batt/history.db ]]; then sudo chown root:"$USER_GROUP" /var/lib/pi-batt/history.db; sudo chmod 664 /var/lib/pi-batt/history.db; fi

sudo cp pi-batt.service /etc/systemd/system/pi-batt.service
sudo cp pi-batt-app.desktop /usr/share/applications/pi-batt.desktop
sudo cp pi-batt.desktop /etc/xdg/autostart/pi-batt.desktop

# Remove old per-user PiUPS launchers so only Pi-Batt starts at login.
rm -f "$HOME/.config/autostart/piups.desktop" "$HOME/.local/share/applications/piups.desktop" 2>/dev/null || true
sudo rm -f /usr/local/bin/piups /usr/local/bin/piupsctl 2>/dev/null || true

sudo systemctl daemon-reload
sudo systemctl enable --now pi-batt.service

echo
echo "Pi-Batt installed."
echo "Daemon status: sudo systemctl status pi-batt --no-pager"
echo "Live data:     pi-battctl status"
echo "GUI now:       pi-batt"
echo
echo "Your existing PiUPS history/config were migrated when found."
echo "The old /opt/piups directory is intentionally left in place as a manual fallback."
echo "Automatic shutdown and HAT physical power-cut remain OFF unless you previously enabled them."
