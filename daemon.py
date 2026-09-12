#!/usr/bin/env python3
import json
import os
import signal
import sqlite3
import subprocess
import sys
import time
from collections import deque
from pathlib import Path
from tempfile import NamedTemporaryFile

from pibatt_hw import UPSHatE

VERSION_PATH = Path("/opt/pi-batt/VERSION")
UPDATE_REQUEST_PATH = Path("/var/lib/pi-batt/update-request.json")
UPDATE_STATUS_PATH = Path("/run/pi-batt/update-status.json")

APP = "Pi-Batt"
CONFIG_PATH = Path("/etc/pi-batt/config.json")
STATE_DIR = Path("/var/lib/pi-batt")
RUN_DIR = Path("/run/pi-batt")
DB_PATH = STATE_DIR / "history.db"
STATUS_PATH = RUN_DIR / "status.json"

DEFAULT_CONFIG = {
    "poll_seconds": 2,
    "history_interval_seconds": 15,
    "history_retention_days": 90,
    "warning_percent": 20,
    "critical_percent": 10,
    "shutdown_percent": 5,
    "shutdown_confirm_seconds": 20,
    "shutdown_countdown_seconds": 60,
    "emergency_cell_mv": 3000,
    "shutdown_enabled": False,
    "trigger_hat_power_cut": False,
    "auto_start_on_power": True,
    "event_debounce_seconds": 6,
    "auto_update_check": True,
    "update_check_hours": 6,
    "cell_capacity_mah": 5000,
    "series_cells": 4,
    "parallel_strings": 1,
    "nominal_cell_voltage_v": 3.7,
    "compact_dashboard": False,
}

running = True

def log(msg):
    print(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {msg}", flush=True)

def handle_signal(_sig, _frame):
    global running
    running = False

def load_config():
    cfg = DEFAULT_CONFIG.copy()
    try:
        with CONFIG_PATH.open() as f:
            cfg.update(json.load(f))
    except FileNotFoundError:
        pass
    except Exception as e:
        log(f"Config read error: {e}; using defaults")
    return cfg

def init_db(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS samples (
            ts INTEGER PRIMARY KEY,
            battery_percent INTEGER,
            battery_voltage_mv INTEGER,
            battery_current_ma INTEGER,
            remaining_capacity_mah INTEGER,
            remaining_discharge_min INTEGER,
            remaining_charge_min INTEGER,
            vbus_powered INTEGER,
            vbus_voltage_mv INTEGER,
            vbus_current_ma INTEGER,
            vbus_power_mw INTEGER,
            cell1_mv INTEGER,
            cell2_mv INTEGER,
            cell3_mv INTEGER,
            cell4_mv INTEGER,
            cell_delta_mv INTEGER,
            charge_state TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts INTEGER NOT NULL,
            event_type TEXT NOT NULL,
            details TEXT
        )
    """)
    conn.commit()

def add_event(conn, event_type, details=""):
    conn.execute("INSERT INTO events(ts,event_type,details) VALUES(?,?,?)", (int(time.time()), event_type, details))
    conn.commit()
    log(f"EVENT {event_type}: {details}")

def insert_sample(conn, d):
    c = d["cells_mv"]
    conn.execute("""
        INSERT OR REPLACE INTO samples VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (
        int(d["timestamp"]), d["battery_percent"], d["battery_voltage_mv"], d["battery_current_ma"],
        d["remaining_capacity_mah"], d["remaining_discharge_min"], d["remaining_charge_min"],
        int(d["vbus_powered"]), d["vbus_voltage_mv"], d["vbus_current_ma"], d["vbus_power_mw"],
        c[0], c[1], c[2], c[3], d["cell_delta_mv"], d["charge_state"]
    ))
    conn.commit()

def cleanup_history(conn, days):
    cutoff = int(time.time()) - int(days) * 86400
    conn.execute("DELETE FROM samples WHERE ts < ?", (cutoff,))
    conn.execute("DELETE FROM events WHERE ts < ?", (cutoff,))
    conn.commit()

def atomic_json(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile("w", dir=path.parent, delete=False) as tf:
        json.dump(obj, tf, indent=2)
        temp = tf.name
    os.chmod(temp, 0o644)
    os.replace(temp, path)

def fmt_eta(minutes):
    if minutes is None or minutes < 0 or minutes > 7 * 24 * 60:
        return None
    h, m = divmod(int(minutes), 60)
    if h:
        return f"{h}h {m:02d}m"
    return f"{m}m"

def main():
    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    os.chmod(RUN_DIR, 0o775)

    conn = sqlite3.connect(DB_PATH)
    init_db(conn)
    cfg = load_config()
    cfg_mtime = CONFIG_PATH.stat().st_mtime if CONFIG_PATH.exists() else 0
    hw = None
    current_samples = deque(maxlen=60)
    last_history = 0
    last_cleanup = 0
    last_vbus_raw = None
    last_vbus_change = time.monotonic()
    stable_vbus = None
    low_since = None
    shutdown_deadline = None
    shutdown_started = False
    last_error_event = 0

    try:
        app_ver = VERSION_PATH.read_text().strip()
    except Exception:
        app_ver = "unknown"
    add_event(conn, "daemon_started", f"Pi-Batt v{app_ver} monitor started")

    try:
        while running:
            loop_start = time.monotonic()
            try:
                if CONFIG_PATH.exists():
                    mt = CONFIG_PATH.stat().st_mtime
                    if mt != cfg_mtime:
                        cfg = load_config()
                        cfg_mtime = mt
                        add_event(conn, "config_reloaded", "Configuration changed")

                # Update requests are intentionally narrow: unprivileged GUI users may
                # ask the root daemon to install or verify only the official GitHub release.
                if UPDATE_REQUEST_PATH.exists():
                    try:
                        req = json.loads(UPDATE_REQUEST_PATH.read_text())
                    except Exception:
                        req = {}
                    try:
                        UPDATE_REQUEST_PATH.unlink()
                    except Exception:
                        pass
                    action = req.get("action")
                    cmd = None
                    if action == "install_latest":
                        cmd = ["/usr/bin/python3", "/opt/pi-batt/updater.py", "--install-latest"]
                    elif action == "reinstall_latest":
                        cmd = ["/usr/bin/python3", "/opt/pi-batt/updater.py", "--install-latest", "--force"]
                    elif action == "verify_latest":
                        cmd = ["/usr/bin/python3", "/opt/pi-batt/updater.py", "--verify-latest"]
                    if cmd:
                        unit = f"pi-batt-update-{int(time.time())}"
                        subprocess.Popen([
                            "/usr/bin/systemd-run", "--unit", unit, "--collect", "--property=Type=oneshot", *cmd
                        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                        add_event(conn, "update_requested", action)

                if hw is None:
                    hw = UPSHatE()

                d = hw.read_all()
                now = time.time()
                d["timestamp"] = now
                d["connected"] = True

                # Debounce mains/VBUS transitions.
                raw_vbus = d["vbus_powered"]
                if last_vbus_raw is None or raw_vbus != last_vbus_raw:
                    last_vbus_raw = raw_vbus
                    last_vbus_change = time.monotonic()
                if stable_vbus is None:
                    stable_vbus = raw_vbus
                elif raw_vbus != stable_vbus and time.monotonic() - last_vbus_change >= cfg["event_debounce_seconds"]:
                    stable_vbus = raw_vbus
                    add_event(conn, "mains_restored" if stable_vbus else "mains_lost", f"Battery {d['battery_percent']}%")
                d["vbus_powered_stable"] = bool(stable_vbus)

                # Current-based rolling ETA supplements the fuel-gauge ETA.
                current_samples.append(d["battery_current_ma"])
                avg_current = sum(current_samples) / len(current_samples)
                d["rolling_battery_current_ma"] = round(avg_current, 1)
                # Signed battery power: positive while charging, negative while discharging.
                d["battery_power_mw"] = int((d["battery_voltage_mv"] * d["battery_current_ma"]) / 1000)
                calculated_eta = None
                if avg_current < -50 and d["remaining_capacity_mah"] > 0:
                    calculated_eta = int((d["remaining_capacity_mah"] / abs(avg_current)) * 60)
                d["calculated_discharge_min"] = calculated_eta

                native_eta = d["remaining_charge_min"] if d["charging"] else d["remaining_discharge_min"]
                d["eta_source"] = "native"
                if not d["charging"] and native_eta is None:
                    native_eta = calculated_eta
                    d["eta_source"] = "calculated" if calculated_eta is not None else "unavailable"
                elif native_eta is None:
                    d["eta_source"] = "unavailable"
                d["eta_minutes"] = native_eta
                d["eta_text"] = fmt_eta(native_eta)
                d["mode"] = "Charging" if d["charging"] else ("On AC" if stable_vbus else "On battery")
                if d["charge_state_code"] == 5:
                    d["mode"] = "Full"

                # Apply desired auto-start configuration without hammering the register.
                if bool(d["auto_start_on_power"]) != bool(cfg["auto_start_on_power"]):
                    d["auto_start_on_power"] = hw.set_auto_start_on_power(bool(cfg["auto_start_on_power"]))
                    add_event(conn, "auto_start_changed", str(d["auto_start_on_power"]))

                # Shutdown state machine. Disabled by default until explicitly enabled in GUI.
                on_battery = not bool(stable_vbus)
                min_cell = min(d["cells_mv"])
                low_condition = on_battery and (
                    d["battery_percent"] <= int(cfg["shutdown_percent"]) or
                    min_cell <= int(cfg["emergency_cell_mv"])
                )

                if not cfg["shutdown_enabled"] or not low_condition:
                    low_since = None
                    if shutdown_deadline is not None and not shutdown_started:
                        add_event(conn, "shutdown_cancelled", "Power restored or battery recovered")
                    shutdown_deadline = None
                else:
                    if low_since is None:
                        low_since = time.monotonic()
                        add_event(conn, "low_battery_detected", f"{d['battery_percent']}%, min cell {min_cell}mV")
                    if shutdown_deadline is None and time.monotonic() - low_since >= int(cfg["shutdown_confirm_seconds"]):
                        shutdown_deadline = time.monotonic() + int(cfg["shutdown_countdown_seconds"])
                        add_event(conn, "shutdown_countdown", f"{cfg['shutdown_countdown_seconds']} seconds")

                d["shutdown_enabled"] = bool(cfg["shutdown_enabled"])
                d["shutdown_pending"] = shutdown_deadline is not None
                d["shutdown_countdown"] = max(0, int(shutdown_deadline - time.monotonic())) if shutdown_deadline else None
                d["warning_level"] = (
                    "critical" if d["battery_percent"] <= int(cfg["critical_percent"]) else
                    "warning" if d["battery_percent"] <= int(cfg["warning_percent"]) else "normal"
                )

                atomic_json(STATUS_PATH, d)

                if now - last_history >= int(cfg["history_interval_seconds"]):
                    insert_sample(conn, d)
                    last_history = now
                if now - last_cleanup >= 86400:
                    cleanup_history(conn, cfg["history_retention_days"])
                    last_cleanup = now

                if shutdown_deadline and time.monotonic() >= shutdown_deadline and not shutdown_started:
                    shutdown_started = True
                    add_event(conn, "shutdown_now", f"Battery {d['battery_percent']}%")
                    if cfg["trigger_hat_power_cut"]:
                        try:
                            hw.trigger_power_cut()
                            add_event(conn, "hat_power_cut_armed", "MCU power cut scheduled (~30 seconds)")
                        except Exception as e:
                            add_event(conn, "hat_power_cut_failed", str(e))
                    subprocess.run(["/usr/bin/systemctl", "poweroff"], check=False)
                    time.sleep(10)

            except Exception as e:
                if hw is not None:
                    hw.close()
                    hw = None
                now = time.time()
                status = {
                    "timestamp": now,
                    "connected": False,
                    "error": str(e),
                    "shutdown_enabled": bool(cfg.get("shutdown_enabled", False)),
                }
                atomic_json(STATUS_PATH, status)
                if now - last_error_event > 60:
                    add_event(conn, "i2c_error", str(e))
                    last_error_event = now

            delay = max(0.2, float(cfg["poll_seconds"]) - (time.monotonic() - loop_start))
            time.sleep(delay)
    finally:
        if hw:
            hw.close()
        conn.close()

if __name__ == "__main__":
    main()
