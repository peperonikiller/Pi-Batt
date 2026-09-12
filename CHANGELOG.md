# Changelog

## 1.0.3
- Redesign the GUI again for smaller Raspberry Pi displays with tighter spacing and improved readability.
- Make all major tabs scrollable so the interface remains usable on shorter screens.
- Rebuild the dashboard into compact battery and input/status sections with smaller metric cards.
- Improve settings usability with better control sizing and more consistent form spacing.
- Rework the updater tab into a more compact two-row action layout for reduced-width displays.
- Reduce the default window size and minimum size to better fit portable and embedded Pi screens.

## 1.0.2
- Redesign the Pi-Batt GUI with a modern dark dashboard, status hero card, battery bar, cleaner metric cards, and improved tab styling.
- Reorganize Settings into clearer battery, shutdown, and general sections.
- Improve Diagnostics layout and recent-events presentation.
- Fix settings-save permissions by making `/etc/pi-batt` group-writable for the installing desktop user.
- Treat the IP2368 controller as idle during normal battery operation instead of incorrectly showing a hard error.
- Add clearer shutdown-protection state colors and dashboard input/ETA summary.
- Add a documented hardware compatibility matrix and clarify that the current backend targets the Waveshare UPS HAT (E) protocol.

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
