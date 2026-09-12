# Pi-Batt v1.0.2

Pi-Batt is a Raspberry Pi desktop + system service monitor for the Waveshare UPS HAT (E). It began as PiUPS and was renamed before the first public release.

## v1.0.2 UI and reliability update

Version 1.0.2 refreshes the desktop experience with a dark card-based dashboard, a large battery/status header, clearer settings sections, improved diagnostics, and corrected IP2368 battery-mode reporting. It also fixes the `/etc/pi-batt` directory permissions required for atomic settings saves.

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

## First install / migration from PiUPS

Run as the normal desktop user, not root:

```bash
cd ~/Pi-Batt
chmod +x install.sh
./install.sh
```

The installer automatically migrates the old PiUPS config and SQLite history when they exist, disables the old `piups.service`, and installs the new Pi-Batt service and launchers. The old `/opt/piups` folder is left untouched as a fallback.

Installed locations:

- `/opt/pi-batt/` — application
- `/etc/pi-batt/config.json` — settings
- `/var/lib/pi-batt/history.db` — history
- `/run/pi-batt/status.json` — live UPS state
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

## Updater design

Pi-Batt checks the public GitHub Releases API for:

`peperonikiller/Pi-Batt`

Every public stable release must include these two assets with matching version numbers:

- `Pi-Batt-vX.Y.Z.zip`
- `Pi-Batt-vX.Y.Z.zip.sha256`

The ZIP must contain `manifest.json` and `VERSION`. The updater refuses to install a package when the checksum, product name, version, or required payload files do not match.

The GUI itself never installs files as root. It writes a narrow update request to `/run/pi-batt/update-request.json`. The root monitoring daemon accepts only three fixed actions—verify latest, install latest, or reinstall latest—and launches the updater in a separate transient systemd unit. Arbitrary URLs or shell commands are not accepted.

## Build release assets

On Linux:

```bash
./make_release.sh
```

This creates:

```text
dist/Pi-Batt-v1.0.2.zip
dist/Pi-Batt-v1.0.2.zip.sha256
```

Upload both files to the matching GitHub Release.

## First updater validation

After publishing a matching GitHub release and uploading the ZIP + SHA256 assets:

1. Open Pi-Batt → **Updates**.
2. Click **Check for updates**. It should report that the installed version is current.
3. Click **Verify release package**. This downloads the GitHub asset, validates SHA256, extracts it, validates the manifest, and Python-compiles the payload without replacing your installed copy.
4. Click **Reinstall latest** to exercise the complete self-update path on the same release.
5. Accept **Restart Pi-Batt** when prompted.
6. Confirm `pi-battctl status` and the dashboard still work.

After those tests pass, future releases only require incrementing `VERSION`/app version/manifest, publishing the new release, and uploading its ZIP + SHA256 assets.

## Safety

Automatic low-battery shutdown and the HAT MCU physical power-cut command remain safety-sensitive features. The updater does not change those settings.
