# Pi-Batt v1.1.5

Pi-Batt is a Raspberry Pi desktop + system service monitor for the Waveshare UPS HAT (E).

## v1.1.5 touch and battery intelligence update

Version 1.1.5 adds smooth battery-bar animation and touch-friendly kinetic scrolling alongside battery pack profiling, estimated battery health, smarter runtime estimates, Raspberry Pi system monitoring, expanded 30-day statistics, a compact-dashboard option, and one-click diagnostic copying. It also keeps updater requests in persistent state storage so reboots do not break update-request permissions.

### New in 1.1.5

- Smooth animated battery percentage bar instead of abrupt percentage jumps.
- Touch-friendly kinetic scrolling: drag/swipe pages, event history, and release notes directly with a finger.
- Configure cell capacity, series count, parallel strings, and nominal cell voltage.
- Automatic pack calculations for S/P layout, pack mAh, nominal voltage, and Wh.
- New Health tab with estimated full-charge capacity, health %, health state, capacity trend, cell balance, and high/low cell values.
- Raspberry Pi CPU temperature, load, RAM usage, and throttling/undervoltage flags.
- HAT-native ETA and independent Pi-Batt runtime ETA shown side-by-side.
- 30-day average charge/discharge power, minimum battery %, maximum cell spread, total outage time, and longest outage.
- Optional compact dashboard mode for very small screens.
- Copy Diagnostics button for quick troubleshooting reports.
- Updater requests now use `/var/lib/pi-batt/update-request.json` instead of `/run`, avoiding reboot-time permission loss.

Battery-health values are estimates based on the configured design capacity and BQ4050-reported remaining capacity. They are intended as a trend/maintenance aid rather than a laboratory state-of-health measurement.

## Hardware compatibility

Pi-Batt currently supports the **Waveshare UPS HAT (E), SKU 27966** and hardware-identical rebrands that implement the exact same I2C MCU register map. Other Waveshare UPS HAT variants (B/C/D/original) use different telemetry hardware/protocols and are not yet supported. See [`HARDWARE_COMPATIBILITY.md`](HARDWARE_COMPATIBILITY.md) for the full compatibility matrix and protocol details.

## Features

- Live battery %, voltage, current, remaining capacity and native UPS ETA
- USB-C input voltage/current/power and charge state
- Per-cell voltage and imbalance monitoring
- Tray/taskbar status with power-loss/restore notifications
- SQLite history with graphs and outage/event logging
- Configurable graceful low-battery shutdown protection
- Auto-start-on-external-power control
- GitHub Releases updater with automatic update checks
- SHA256 verification and release-manifest validation before installation
- Automatic backup of the currently installed `/opt/pi-batt` before updates
- One-click release-package verification and same-version reinstall for testing the updater

## First install

Run as the normal desktop user, not root:

```bash
cd ~/Pi-Batt
chmod +x install.sh
./install.sh
```



Installed locations:

- `/opt/pi-batt/` — application
- `/etc/pi-batt/config.json` — settings
- `/var/lib/pi-batt/history.db` — history
- `/run/pi-batt/status.json` — live UPS state
- `/var/lib/pi-batt/update-request.json` — narrow GUI-to-service updater request
- `/usr/local/bin/pi-batt` — Wayland-aware GUI launcher
- `/usr/local/bin/pi-battctl` — CLI status helper
- `pi-batt.service` — root background monitor

## Launch

```bash
pi-batt
```

Tray-only mode:

```bash
pi-batt --tray
```

CLI status:

```bash
pi-battctl status
sudo systemctl status pi-batt --no-pager
sudo journalctl -u pi-batt -f
```



