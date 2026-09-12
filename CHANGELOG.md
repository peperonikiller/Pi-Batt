# Changelog

## 1.0.1
- Fix repeated restart prompt after updater completes.
- Add single-instance protection for the tray app.
- Add battery power, rolling current, ETA source, and sample age to the dashboard.
- Add battery-power history graph.
- Add outage summary statistics to Diagnostics.
- Add low-condition confirmation setting and threshold validation.
- Add desktop notification test button.
- Improve updater resilience with rollback on copy failure and backup pruning.

## 1.0.0

- Renamed the project from PiUPS to Pi-Batt.
- Added GitHub Releases update checking in the desktop app.
- Added checksum-verified self-updating through the root monitoring service.
- Added release package verification and same-version reinstall for updater testing.
- Added automatic migration of PiUPS configuration and history.
- Preserved dashboard, tray, history, diagnostics, native UPS ETA, and shutdown safety features.
