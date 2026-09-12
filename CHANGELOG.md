# Changelog

## 1.1.5
- Add smooth animated battery percentage bar transitions using Qt property animation.
- Preserve touch-friendly kinetic scrolling and compact-screen controls from the v1.1 work.
- Include the full v1.1 battery intelligence feature set: pack profiling, health estimation, smarter ETA, Pi system monitoring, battery statistics, compact dashboard mode, and Copy Diagnostics.
- Keep updater requests in persistent `/var/lib/pi-batt` storage to avoid reboot-time permissions failures.

## 1.1.0
- Add touch-friendly kinetic scrolling: drag anywhere in scrollable tabs, event history, and release notes with a finger instead of grabbing the scrollbar.
- Enable per-pixel scrolling and tab overflow buttons for compact touch displays.
- Add configurable battery pack profile: cell mAh, series cells, parallel strings, and nominal cell voltage.
- Calculate pack configuration, total pack mAh, nominal voltage, and nominal watt-hours.
- Add a Health tab with estimated full-charge capacity, health percentage/state, capacity trend, cell balance, and cell high/low values.
- Add Raspberry Pi CPU temperature, load average, RAM usage, and throttling/undervoltage status.
- Add Pi-Batt runtime ETA alongside the UPS HAT native ETA, with native ETA preferred when available.
- Add 30-day battery statistics for average discharge/charge power, minimum battery %, maximum cell spread, total outage time, and longest outage.
- Add optional compact dashboard mode for very small screens.
- Add Copy Diagnostics for quick support/troubleshooting reports.
- Move GUI updater requests from `/run/pi-batt` to persistent `/var/lib/pi-batt` storage to prevent reboot-time permissions failures.

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
