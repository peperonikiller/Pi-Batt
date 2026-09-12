#!/usr/bin/env python3
import json
import math
import os
import sqlite3
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path

from PyQt5.QtCore import Qt, QTimer, QPointF, QThread, pyqtSignal, QProcess, QLockFile
from PyQt5.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap, QFont
from PyQt5.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QFormLayout, QGridLayout, QGroupBox,
    QHBoxLayout, QLabel, QMainWindow, QMessageBox, QPushButton, QSpinBox,
    QSystemTrayIcon, QTabWidget, QTableWidget, QTableWidgetItem, QVBoxLayout,
    QWidget, QTextEdit, QProgressBar, QFrame, QSizePolicy
)

CONFIG_PATH = Path("/etc/pi-batt/config.json")
STATUS_PATH = Path("/run/pi-batt/status.json")
DB_PATH = Path("/var/lib/pi-batt/history.db")
VERSION_FILE = Path(__file__).resolve().with_name("VERSION")
try:
    APP_VERSION = VERSION_FILE.read_text().strip()
except Exception:
    APP_VERSION = "1.0.0"
GITHUB_REPO = "peperonikiller/Pi-Batt"
UPDATE_REQUEST_PATH = Path("/run/pi-batt/update-request.json")
UPDATE_STATUS_PATH = Path("/run/pi-batt/update-status.json")

DEFAULT_CONFIG = {
    "warning_percent": 20, "critical_percent": 10, "shutdown_percent": 5,
    "shutdown_confirm_seconds": 20, "shutdown_countdown_seconds": 60,
    "emergency_cell_mv": 3000, "shutdown_enabled": False,
    "trigger_hat_power_cut": False, "auto_start_on_power": True,
    "history_interval_seconds": 15, "history_retention_days": 90,
    "poll_seconds": 2, "event_debounce_seconds": 6,
    "auto_update_check": True, "update_check_hours": 6
}


def version_tuple(value):
    s = str(value).strip().lstrip("vV").split("-", 1)[0]
    try:
        return tuple(int(x) for x in s.split("."))
    except Exception:
        return (0,)


APP_STYLESHEET = r"""
QMainWindow, QWidget {
    background: #0f1722;
    color: #dce7f5;
    font-size: 10.5pt;
}
QTabWidget::pane {
    border: 1px solid #26364c;
    border-radius: 10px;
    background: #111b29;
    top: -1px;
}
QTabBar::tab {
    background: transparent;
    color: #8ea0b7;
    padding: 11px 17px;
    margin-right: 3px;
    border-bottom: 3px solid transparent;
    font-weight: 600;
}
QTabBar::tab:selected {
    color: #eef7ff;
    border-bottom: 3px solid #42c6ff;
}
QTabBar::tab:hover { color: #ffffff; background: #162235; }
QFrame#heroCard, QGroupBox {
    background: #172235;
    border: 1px solid #2a3a51;
    border-radius: 12px;
}
QFrame#heroCard { background: #142033; }
QGroupBox {
    margin-top: 11px;
    padding: 14px 12px 12px 12px;
    font-weight: 600;
    color: #9db0c8;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 6px;
    color: #8fa5bf;
}
QGroupBox#metricCard {
    min-height: 80px;
    background: #18263a;
}
QLabel#heroPercent {
    color: #ffffff;
    font-size: 38pt;
    font-weight: 800;
}
QLabel#modeBadge {
    background: #203149;
    color: #dff4ff;
    border: 1px solid #36516e;
    border-radius: 12px;
    padding: 6px 12px;
    font-weight: 700;
}
QLabel#muted { color: #8699b2; }
QLabel#sectionTitle {
    font-size: 18pt;
    font-weight: 750;
    color: #f4f8fc;
}
QLabel#shutdownBanner {
    border-radius: 9px;
    padding: 9px 12px;
    background: #132b27;
    border: 1px solid #24544a;
    color: #9ee8d1;
    font-weight: 600;
}
QProgressBar#batteryBar {
    background: #0d1520;
    border: 1px solid #2c4058;
    border-radius: 7px;
    min-height: 13px;
    max-height: 13px;
}
QProgressBar#batteryBar::chunk {
    background: #48d597;
    border-radius: 6px;
}
QPushButton {
    background: #21334b;
    border: 1px solid #36506e;
    border-radius: 8px;
    padding: 8px 14px;
    color: #e9f4ff;
    font-weight: 600;
}
QPushButton:hover { background: #2a4160; border-color: #4b729b; }
QPushButton:pressed { background: #19293d; }
QPushButton:disabled { color: #64758b; background: #172231; border-color: #26364a; }
QPushButton#primaryButton { background: #1579a8; border-color: #38bdf8; }
QPushButton#primaryButton:hover { background: #188dbf; }
QSpinBox, QComboBox, QTextEdit {
    background: #101a28;
    border: 1px solid #31445d;
    border-radius: 7px;
    padding: 6px 8px;
    color: #e4edf7;
    selection-background-color: #237ca7;
}
QSpinBox:focus, QComboBox:focus, QTextEdit:focus { border-color: #42c6ff; }
QCheckBox { spacing: 9px; padding: 4px 0; }
QTableWidget {
    background: #101a28;
    alternate-background-color: #142133;
    border: 1px solid #2a3b52;
    border-radius: 8px;
    gridline-color: #24354b;
    color: #d9e6f3;
}
QHeaderView::section {
    background: #1a2a40;
    color: #a9bcd2;
    border: none;
    border-right: 1px solid #2b3d54;
    padding: 7px;
    font-weight: 700;
}
QToolTip { background: #1a2738; color: white; border: 1px solid #40556f; }
"""

def apply_app_style(app):
    app.setStyleSheet(APP_STYLESHEET)

class UpdateCheckWorker(QThread):
    result = pyqtSignal(dict)
    failed = pyqtSignal(str)

    def run(self):
        try:
            url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
            req = urllib.request.Request(url, headers={
                "User-Agent": f"Pi-Batt/{APP_VERSION}",
                "Accept": "application/vnd.github+json",
            })
            with urllib.request.urlopen(req, timeout=12) as r:
                data = json.load(r)
            tag = data.get("tag_name", "")
            ver = tag.lstrip("vV")
            self.result.emit({
                "tag": tag,
                "version": ver,
                "name": data.get("name") or tag,
                "body": data.get("body") or "",
                "url": data.get("html_url") or "",
                "published_at": data.get("published_at") or "",
                "update_available": version_tuple(ver) > version_tuple(APP_VERSION),
            })
        except Exception as e:
            self.failed.emit(str(e))

def read_json(path, default=None):
    try:
        with path.open() as f:
            return json.load(f)
    except Exception:
        return default

def human_eta(minutes):
    if minutes is None:
        return "—"
    try: minutes = int(minutes)
    except Exception: return "—"
    if minutes < 0 or minutes > 10080:
        return "—"
    h, m = divmod(minutes, 60)
    return f"{h}h {m:02d}m" if h else f"{m} min"

def make_battery_icon(percent=0, charging=False, connected=True):
    pm = QPixmap(48, 48)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    outline = QColor(230, 230, 230) if connected else QColor(130, 130, 130)
    p.setPen(QPen(outline, 3))
    p.drawRoundedRect(7, 12, 31, 24, 4, 4)
    p.drawRect(39, 19, 4, 10)
    fill_w = max(0, min(27, round(27 * percent / 100)))
    if connected:
        color = QColor(80, 190, 100) if percent > 20 else QColor(230, 170, 50) if percent > 10 else QColor(220, 70, 70)
    else:
        color = QColor(100, 100, 100)
    p.fillRect(9, 14, fill_w, 20, color)
    if charging:
        p.setPen(QPen(QColor(255,255,255), 3))
        p.drawLine(25, 14, 19, 24)
        p.drawLine(19, 24, 26, 24)
        p.drawLine(26, 24, 21, 34)
    p.end()
    return QIcon(pm)

class MiniChart(QWidget):
    def __init__(self):
        super().__init__()
        self.points = []
        self.y_min = 0
        self.y_max = 100
        self.title = "Battery %"
        self.setMinimumHeight(260)

    def set_data(self, points, y_min=0, y_max=100, title="Battery %"):
        self.points = points
        self.y_min, self.y_max, self.title = y_min, y_max, title
        self.update()

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = self.rect().adjusted(50, 24, -20, -40)
        p.setPen(QColor("#dce7f5"))
        p.drawText(10, 18, self.title)
        if len(self.points) < 2:
            p.drawText(r, Qt.AlignCenter, "Waiting for history data…")
            return
        grid = QColor("#34465d")
        p.setPen(QPen(grid, 1))
        for i in range(5):
            y = r.top() + i * r.height() / 4
            p.drawLine(r.left(), int(y), r.right(), int(y))
            val = self.y_max - (self.y_max - self.y_min) * i / 4
            p.drawText(2, int(y)+5, f"{val:.0f}")
        xs = [x for x,_ in self.points]
        ys = [y for _,y in self.points]
        xmin, xmax = min(xs), max(xs)
        span = max(1, xmax-xmin)
        yrange = max(1e-6, self.y_max-self.y_min)
        path = QPainterPath()
        for i, (x,y) in enumerate(self.points):
            px = r.left() + (x-xmin)/span*r.width()
            py = r.bottom() - (y-self.y_min)/yrange*r.height()
            py = max(r.top(), min(r.bottom(), py))
            if i == 0: path.moveTo(QPointF(px,py))
            else: path.lineTo(QPointF(px,py))
        accent = QColor("#42c6ff")
        p.setPen(QPen(accent, 3))
        p.drawPath(path)
        p.setPen(QColor("#91a5bc"))
        p.drawText(r.left(), r.bottom()+25, time.strftime("%m/%d %H:%M", time.localtime(xmin)))
        end = time.strftime("%m/%d %H:%M", time.localtime(xmax))
        p.drawText(r.right()-120, r.bottom()+25, 120, 20, Qt.AlignRight, end)

class MainWindow(QMainWindow):
    def __init__(self, tray):
        super().__init__()
        self.tray = tray
        self.last = None
        self.prev_vbus = None
        self.prev_warning = "normal"
        self.setWindowTitle(f"Pi-Batt v{APP_VERSION}")
        self.resize(980, 720)
        self.setMinimumSize(860, 640)

        tabs = QTabWidget(); tabs.setDocumentMode(True); self.setCentralWidget(tabs)
        self.dashboard = QWidget(); self.history = QWidget(); self.settings = QWidget(); self.diag = QWidget(); self.updates = QWidget()
        tabs.addTab(self.dashboard, "Dashboard")
        tabs.addTab(self.history, "History")
        tabs.addTab(self.settings, "Settings")
        tabs.addTab(self.diag, "Diagnostics")
        tabs.addTab(self.updates, "Updates")
        self.build_dashboard(); self.build_history(); self.build_settings(); self.build_diag(); self.build_updates()

        self.timer = QTimer(self); self.timer.timeout.connect(self.refresh); self.timer.start(2000)
        self.history_timer = QTimer(self); self.history_timer.timeout.connect(self.refresh_history); self.history_timer.start(30000)
        self.refresh(); self.refresh_history()
        # Treat any updater result that predates this GUI process as already acknowledged.
        # This prevents an installed-status file from causing an endless restart prompt.
        self.startup_update_status = read_json(UPDATE_STATUS_PATH, {}) or {}
        self.last_update_stamp = self.startup_update_status.get("timestamp", 0)
        self.apply_startup_update_status()
        self.update_poll_timer = QTimer(self); self.update_poll_timer.timeout.connect(self.poll_update_status); self.update_poll_timer.start(1500)
        cfg = read_json(CONFIG_PATH, DEFAULT_CONFIG.copy()) or DEFAULT_CONFIG.copy()
        if cfg.get("auto_update_check", True):
            QTimer.singleShot(5000, lambda: self.check_updates(silent=True))
            hours = max(1, int(cfg.get("update_check_hours", 6)))
            self.auto_update_timer = QTimer(self); self.auto_update_timer.timeout.connect(lambda: self.check_updates(silent=True)); self.auto_update_timer.start(hours * 3600 * 1000)

    def make_metric_label(self, text="—", big=False):
        l = QLabel(text)
        if big:
            f = l.font(); f.setPointSize(22); f.setBold(True); l.setFont(f)
        return l

    def build_dashboard(self):
        root = QVBoxLayout(self.dashboard)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(14)

        hero = QFrame(); hero.setObjectName("heroCard")
        hero_l = QHBoxLayout(hero); hero_l.setContentsMargins(20, 18, 20, 18); hero_l.setSpacing(22)

        left = QVBoxLayout(); left.setSpacing(4)
        kicker = QLabel("UPS BATTERY") ; kicker.setObjectName("muted")
        self.percent = QLabel("—%") ; self.percent.setObjectName("heroPercent")
        self.battery_bar = QProgressBar(); self.battery_bar.setObjectName("batteryBar"); self.battery_bar.setRange(0,100); self.battery_bar.setTextVisible(False)
        left.addWidget(kicker); left.addWidget(self.percent); left.addWidget(self.battery_bar)
        hero_l.addLayout(left, 2)

        right = QVBoxLayout(); right.setSpacing(7)
        self.mode = QLabel("Waiting…"); self.mode.setObjectName("modeBadge"); self.mode.setAlignment(Qt.AlignCenter)
        self.hero_eta = QLabel("ETA —"); self.hero_eta.setAlignment(Qt.AlignRight); self.hero_eta.setObjectName("sectionTitle")
        self.hero_input = QLabel("Input —"); self.hero_input.setAlignment(Qt.AlignRight); self.hero_input.setObjectName("muted")
        right.addWidget(self.mode, 0, Qt.AlignRight); right.addStretch(); right.addWidget(self.hero_eta); right.addWidget(self.hero_input)
        hero_l.addLayout(right, 1)
        root.addWidget(hero)

        grid = QGridLayout(); grid.setHorizontalSpacing(12); grid.setVerticalSpacing(12); root.addLayout(grid)
        labels = [
            ("ETA", "eta"), ("Battery voltage", "batt_v"), ("Battery current", "batt_i"),
            ("Battery power", "batt_p"), ("Remaining capacity", "capacity"), ("USB-C voltage", "vbus_v"),
            ("USB-C current", "vbus_i"), ("USB-C power", "vbus_p"), ("Cell delta", "delta"),
            ("Rolling current", "rolling_i"), ("ETA source", "eta_source"), ("Last sample", "sample_age")
        ]
        self.metrics = {}
        for idx,(name,key) in enumerate(labels):
            box=QGroupBox(name); box.setObjectName("metricCard")
            lay=QVBoxLayout(box); lay.setContentsMargins(10, 13, 10, 10)
            val=self.make_metric_label("—", True); val.setAlignment(Qt.AlignCenter); lay.addWidget(val)
            self.metrics[key]=val; grid.addWidget(box, idx//4, idx%4)

        cells=QGroupBox("Cell voltages"); cgrid=QGridLayout(cells); cgrid.setHorizontalSpacing(16); self.cell_labels=[]
        for i in range(4):
            name=QLabel(f"CELL {i+1}"); name.setObjectName("muted"); name.setAlignment(Qt.AlignCenter)
            lab=self.make_metric_label("—", True); lab.setAlignment(Qt.AlignCenter); self.cell_labels.append(lab)
            cgrid.addWidget(name,0,i); cgrid.addWidget(lab,1,i)
        root.addWidget(cells)

        self.shutdown_banner=QLabel(""); self.shutdown_banner.setObjectName("shutdownBanner"); self.shutdown_banner.setAlignment(Qt.AlignCenter); root.addWidget(self.shutdown_banner)

    def build_history(self):
        root=QVBoxLayout(self.history); root.setContentsMargins(18,18,18,18); root.setSpacing(12)
        title=QLabel("Battery history"); title.setObjectName("sectionTitle"); root.addWidget(title)
        row=QHBoxLayout(); root.addLayout(row)
        self.range=QComboBox(); self.range.addItems(["24 hours","7 days","30 days","90 days"]); self.range.currentIndexChanged.connect(self.refresh_history)
        self.series=QComboBox(); self.series.addItems(["Battery %","Battery voltage","Battery current","Battery power","Input power","Cell delta"]); self.series.currentIndexChanged.connect(self.refresh_history)
        row.addWidget(QLabel("Range:")); row.addWidget(self.range); row.addSpacing(20); row.addWidget(QLabel("Metric:")); row.addWidget(self.series); row.addStretch()
        self.chart=MiniChart(); root.addWidget(self.chart)

    def build_settings(self):
        root=QVBoxLayout(self.settings); root.setContentsMargins(18,18,18,18); root.setSpacing(14)
        title=QLabel("Power protection settings"); title.setObjectName("sectionTitle"); root.addWidget(title)
        cfg=read_json(CONFIG_PATH, DEFAULT_CONFIG.copy()) or DEFAULT_CONFIG.copy()
        self.s_warning=QSpinBox(); self.s_warning.setRange(1,99); self.s_warning.setSuffix(" %"); self.s_warning.setValue(int(cfg.get("warning_percent",20)))
        self.s_critical=QSpinBox(); self.s_critical.setRange(1,99); self.s_critical.setSuffix(" %"); self.s_critical.setValue(int(cfg.get("critical_percent",10)))
        self.s_shutdown=QSpinBox(); self.s_shutdown.setRange(1,50); self.s_shutdown.setSuffix(" %"); self.s_shutdown.setValue(int(cfg.get("shutdown_percent",5)))
        self.s_confirm=QSpinBox(); self.s_confirm.setRange(5,300); self.s_confirm.setSuffix(" s"); self.s_confirm.setValue(int(cfg.get("shutdown_confirm_seconds",20)))
        self.s_countdown=QSpinBox(); self.s_countdown.setRange(10,600); self.s_countdown.setSuffix(" s"); self.s_countdown.setValue(int(cfg.get("shutdown_countdown_seconds",60)))
        self.s_cell=QSpinBox(); self.s_cell.setRange(2600,3600); self.s_cell.setSuffix(" mV"); self.s_cell.setValue(int(cfg.get("emergency_cell_mv",3000)))
        self.s_retention=QSpinBox(); self.s_retention.setRange(1,3650); self.s_retention.setSuffix(" days"); self.s_retention.setValue(int(cfg.get("history_retention_days",90)))
        self.s_shutdown_enable=QCheckBox("Enable automatic graceful shutdown"); self.s_shutdown_enable.setChecked(bool(cfg.get("shutdown_enabled",False)))
        self.s_cut=QCheckBox("Arm HAT power-cut timer immediately before Linux poweroff"); self.s_cut.setChecked(bool(cfg.get("trigger_hat_power_cut",False)))
        self.s_autostart=QCheckBox("Auto-start Pi when external power returns"); self.s_autostart.setChecked(bool(cfg.get("auto_start_on_power",True)))
        self.s_auto_update=QCheckBox("Automatically check GitHub for Pi-Batt updates"); self.s_auto_update.setChecked(bool(cfg.get("auto_update_check",True)))

        thresholds=QGroupBox("Battery thresholds"); form=QFormLayout(thresholds)
        form.addRow("Low battery warning", self.s_warning); form.addRow("Critical warning", self.s_critical); form.addRow("Shutdown threshold", self.s_shutdown); form.addRow("Emergency minimum cell", self.s_cell)
        timing=QGroupBox("Shutdown behavior"); tf=QFormLayout(timing)
        tf.addRow("Low condition confirmation", self.s_confirm); tf.addRow("Shutdown countdown", self.s_countdown); tf.addRow(self.s_shutdown_enable); tf.addRow(self.s_cut)
        general=QGroupBox("General"); gf=QFormLayout(general)
        gf.addRow("Keep history", self.s_retention); gf.addRow(self.s_autostart); gf.addRow(self.s_auto_update)
        root.addWidget(thresholds); root.addWidget(timing); root.addWidget(general)
        note=QLabel("Safety: the HAT power-cut command is irreversible once armed and cuts power about 30 seconds later. Enable it only after graceful shutdown testing succeeds."); note.setWordWrap(True); note.setObjectName("muted"); root.addWidget(note)
        buttons=QHBoxLayout(); root.addLayout(buttons)
        btn=QPushButton("Save settings"); btn.setObjectName("primaryButton"); btn.clicked.connect(self.save_settings); buttons.addWidget(btn)
        test_btn=QPushButton("Test notification"); test_btn.clicked.connect(lambda: self.tray.showMessage("Pi-Batt test", "Desktop notifications are working.", QSystemTrayIcon.Information, 5000)); buttons.addWidget(test_btn)
        buttons.addStretch(); root.addStretch()

    def build_diag(self):
        root=QVBoxLayout(self.diag); root.setContentsMargins(18,18,18,18); root.setSpacing(12)
        title=QLabel("UPS diagnostics"); title.setObjectName("sectionTitle"); root.addWidget(title)
        self.diag_labels={}
        summary=QGroupBox("Hardware status"); grid=QGridLayout(summary); grid.setHorizontalSpacing(24); grid.setVerticalSpacing(9)
        items=[("Connection","connected"),("Firmware","firmware"),("BQ4050 fuel gauge","bq"),("IP2368 power controller","ip"),("Auto-start","auto"),("Charge state","charge"),("I²C ID","id"),("Outages (24h)","outages24"),("Longest outage (7d)","longest7"),("Current outage","current_outage")]
        for idx,(name,key) in enumerate(items):
            name_l=QLabel(name); name_l.setObjectName("muted")
            val=QLabel("—"); val.setStyleSheet("font-weight: 700;")
            self.diag_labels[key]=val
            col=(idx%2)*2; row=idx//2; grid.addWidget(name_l,row,col); grid.addWidget(val,row,col+1)
        root.addWidget(summary)
        recent=QLabel("Recent events"); recent.setObjectName("sectionTitle"); root.addWidget(recent)
        self.events=QTableWidget(0,3); self.events.setAlternatingRowColors(True); self.events.setHorizontalHeaderLabels(["Time","Event","Details"]); self.events.horizontalHeader().setStretchLastSection(True); root.addWidget(self.events)
        b=QPushButton("Refresh diagnostics"); b.clicked.connect(self.refresh_events); root.addWidget(b,0,Qt.AlignLeft)
        self.refresh_events()

    def apply_startup_update_status(self):
        d = getattr(self, "startup_update_status", {}) or {}
        state = d.get("state")
        msg = d.get("message")
        if not state or not msg:
            return
        # On a freshly restarted GUI, show the previous result as informational state only.
        # Never ask for another restart for the same completed update.
        self.update_state.setText(msg)
        if state == "installed":
            ver = d.get("version", APP_VERSION)
            self.update_latest.setText(f"Installed successfully: v{ver}")

    def build_updates(self):
        root=QVBoxLayout(self.updates); root.setContentsMargins(18,18,18,18); root.setSpacing(12)
        title=QLabel("Pi-Batt updater"); title.setObjectName("sectionTitle"); f=title.font(); f.setPointSize(18); f.setBold(True); title.setFont(f); root.addWidget(title)
        self.update_current=QLabel(f"Installed version: v{APP_VERSION}"); root.addWidget(self.update_current)
        self.update_latest=QLabel("Latest release: not checked yet"); root.addWidget(self.update_latest)
        self.update_state=QLabel("Updater idle"); self.update_state.setWordWrap(True); root.addWidget(self.update_state)
        row=QHBoxLayout(); root.addLayout(row)
        self.btn_check=QPushButton("Check for updates"); self.btn_check.clicked.connect(lambda: self.check_updates(silent=False)); row.addWidget(self.btn_check)
        self.btn_install=QPushButton("Install latest"); self.btn_install.clicked.connect(lambda: self.request_update("install_latest")); self.btn_install.setEnabled(False); row.addWidget(self.btn_install)
        self.btn_verify=QPushButton("Verify release package"); self.btn_verify.clicked.connect(lambda: self.request_update("verify_latest")); row.addWidget(self.btn_verify)
        self.btn_reinstall=QPushButton("Reinstall latest"); self.btn_reinstall.clicked.connect(lambda: self.request_update("reinstall_latest")); row.addWidget(self.btn_reinstall)
        row.addStretch()
        root.addWidget(QLabel("Release notes"))
        self.release_notes=QTextEdit(); self.release_notes.setReadOnly(True); self.release_notes.setPlaceholderText("Release notes will appear here after checking GitHub."); root.addWidget(self.release_notes)
        note=QLabel("Updates are downloaded only from the official GitHub Releases page for peperonikiller/Pi-Batt. Pi-Batt requires a matching .sha256 asset and validates the release manifest before replacing installed files. A backup of /opt/pi-batt is kept before each update.")
        note.setWordWrap(True); root.addWidget(note)

    def check_updates(self, silent=False):
        if hasattr(self, "update_worker") and self.update_worker and self.update_worker.isRunning():
            return
        self.btn_check.setEnabled(False)
        if not silent: self.update_state.setText("Checking GitHub…")
        self.update_worker=UpdateCheckWorker(self)
        self.update_worker.result.connect(lambda data: self.update_check_done(data, silent))
        self.update_worker.failed.connect(lambda err: self.update_check_failed(err, silent))
        self.update_worker.finished.connect(lambda: self.btn_check.setEnabled(True))
        self.update_worker.start()

    def update_check_done(self, data, silent=False):
        ver=data.get("version") or "—"
        self.update_latest.setText(f"Latest release: v{ver}")
        self.release_notes.setPlainText(data.get("body") or "No release notes.")
        available=bool(data.get("update_available"))
        self.btn_install.setEnabled(available)
        if available:
            self.update_state.setText(f"Pi-Batt v{ver} is available.")
            if silent:
                self.tray.showMessage("Pi-Batt update available", f"Version {ver} is ready to install.", QSystemTrayIcon.Information, 6000)
        else:
            self.update_state.setText(f"You're up to date on v{APP_VERSION}.")

    def update_check_failed(self, err, silent=False):
        self.update_state.setText(f"Update check failed: {err}")
        if not silent:
            QMessageBox.warning(self, "Pi-Batt updater", f"Could not check GitHub:\n{err}")

    def request_update(self, action):
        labels={"install_latest":"install the latest release", "reinstall_latest":"reinstall the latest release", "verify_latest":"download and verify the latest release package"}
        if action != "verify_latest":
            if QMessageBox.question(self, "Pi-Batt updater", f"Ready to {labels[action]}?\n\nBattery monitoring continues during download. The daemon restarts briefly while the update is applied.", QMessageBox.Yes|QMessageBox.No) != QMessageBox.Yes:
                return
        try:
            tmp=UPDATE_REQUEST_PATH.with_suffix(".tmp")
            with tmp.open("w") as f: json.dump({"action":action,"requested_at":int(time.time())},f)
            os.replace(tmp,UPDATE_REQUEST_PATH)
            self.update_state.setText("Update request sent to Pi-Batt service…")
        except Exception as e:
            QMessageBox.critical(self,"Pi-Batt updater",f"Could not request update:\n{e}")

    def poll_update_status(self):
        d=read_json(UPDATE_STATUS_PATH)
        if not d: return
        stamp=d.get("timestamp",0)
        if getattr(self,"last_update_stamp",None)==stamp: return
        self.last_update_stamp=stamp
        state=d.get("state","unknown"); msg=d.get("message",state)
        self.update_state.setText(msg)
        busy = state in ("downloading", "installing")
        self.btn_check.setEnabled(not busy); self.btn_verify.setEnabled(not busy); self.btn_reinstall.setEnabled(not busy)
        if state == "installed":
            version=d.get("version","new version")
            if QMessageBox.question(self,"Pi-Batt updated",f"Pi-Batt {version} was installed successfully.\n\nRestart the Pi-Batt tray app now?",QMessageBox.Yes|QMessageBox.No)==QMessageBox.Yes:
                QProcess.startDetached("/usr/local/bin/pi-batt", [])
                QApplication.instance().quit()
        elif state == "verified":
            QMessageBox.information(self,"Pi-Batt updater",msg+"\n\nThe updater download, checksum, and release-manifest validation all passed.")
        elif state == "error":
            QMessageBox.warning(self,"Pi-Batt update failed",msg)

    def save_settings(self):
        if not (self.s_warning.value() > self.s_critical.value() > self.s_shutdown.value()):
            QMessageBox.warning(self, "Pi-Batt settings", "Thresholds must be ordered as: low warning > critical warning > shutdown threshold.")
            return
        cfg=read_json(CONFIG_PATH, DEFAULT_CONFIG.copy()) or DEFAULT_CONFIG.copy()
        cfg.update({
            "warning_percent":self.s_warning.value(), "critical_percent":self.s_critical.value(), "shutdown_percent":self.s_shutdown.value(),
            "shutdown_confirm_seconds":self.s_confirm.value(), "shutdown_countdown_seconds":self.s_countdown.value(), "emergency_cell_mv":self.s_cell.value(), "history_retention_days":self.s_retention.value(),
            "shutdown_enabled":self.s_shutdown_enable.isChecked(), "trigger_hat_power_cut":self.s_cut.isChecked(), "auto_start_on_power":self.s_autostart.isChecked(),
            "auto_update_check":self.s_auto_update.isChecked()
        })
        try:
            tmp=CONFIG_PATH.with_suffix(".tmp")
            with tmp.open("w") as f: json.dump(cfg,f,indent=2)
            os.replace(tmp,CONFIG_PATH)
            QMessageBox.information(self,"Pi-Batt","Settings saved. The daemon will reload them automatically.")
        except Exception as e:
            QMessageBox.critical(self,"Pi-Batt",f"Could not save settings:\n{e}\n\nIf this is the first launch after install, log out/in once so your pi-batt group membership is active.")

    def refresh(self):
        d=read_json(STATUS_PATH)
        if not d:
            self.mode.setText("Daemon unavailable"); self.tray.setIcon(make_battery_icon(0,False,False)); return
        if not d.get("connected",False):
            self.mode.setText("UPS disconnected"); self.tray.setIcon(make_battery_icon(0,False,False)); self.tray.setToolTip("Pi-Batt: UPS disconnected"); return
        pct=int(d.get("battery_percent",0)); charging=bool(d.get("charging",False)); mode=d.get("mode","—")
        self.percent.setText(f"{pct}%"); self.mode.setText(mode)
        self.battery_bar.setValue(pct)
        bar_color = "#48d597" if pct > 20 else "#f6bd4b" if pct > 10 else "#ff6b6b"
        self.battery_bar.setStyleSheet(f"QProgressBar#batteryBar::chunk {{ background: {bar_color}; border-radius: 6px; }}")
        eta_text = human_eta(d.get("eta_minutes"))
        self.hero_eta.setText(f"ETA {eta_text}")
        self.hero_input.setText(f"Input {d.get('vbus_power_mw',0)/1000:.1f} W  •  Battery {d.get('battery_voltage_mv',0)/1000:.2f} V")
        self.metrics["eta"].setText(eta_text)
        self.metrics["batt_v"].setText(f"{d.get('battery_voltage_mv',0)/1000:.3f} V")
        self.metrics["batt_i"].setText(f"{d.get('battery_current_ma',0)/1000:+.3f} A")
        self.metrics["batt_p"].setText(f"{d.get('battery_power_mw',0)/1000:+.2f} W")
        self.metrics["capacity"].setText(f"{d.get('remaining_capacity_mah',0)} mAh")
        self.metrics["vbus_v"].setText(f"{d.get('vbus_voltage_mv',0)/1000:.3f} V")
        self.metrics["vbus_i"].setText(f"{d.get('vbus_current_ma',0)/1000:+.3f} A")
        self.metrics["vbus_p"].setText(f"{d.get('vbus_power_mw',0)/1000:.2f} W")
        self.metrics["delta"].setText(f"{d.get('cell_delta_mv',0)} mV")
        self.metrics["rolling_i"].setText(f"{d.get('rolling_battery_current_ma',0)/1000:+.3f} A")
        self.metrics["eta_source"].setText(str(d.get("eta_source","—")).title())
        age=max(0, int(time.time()-float(d.get("timestamp",time.time())))); self.metrics["sample_age"].setText(f"{age} s ago")
        for i,v in enumerate(d.get("cells_mv",[0,0,0,0])): self.cell_labels[i].setText(f"{v/1000:.3f} V")
        if d.get("shutdown_pending"):
            self.shutdown_banner.setText(f"⚠ Automatic shutdown in {d.get('shutdown_countdown',0)} seconds — reconnect external power to cancel")
            self.shutdown_banner.setStyleSheet("background:#3b1c22;border:1px solid #7b3340;color:#ffb1bd;border-radius:9px;padding:9px 12px;font-weight:700;")
        elif d.get("shutdown_enabled"):
            self.shutdown_banner.setText("✓ Automatic shutdown protection enabled")
            self.shutdown_banner.setStyleSheet("background:#132b27;border:1px solid #24544a;color:#9ee8d1;border-radius:9px;padding:9px 12px;font-weight:700;")
        else:
            self.shutdown_banner.setText("Automatic shutdown protection is disabled")
            self.shutdown_banner.setStyleSheet("background:#302717;border:1px solid #66532a;color:#f3d68e;border-radius:9px;padding:9px 12px;font-weight:700;")

        icon=make_battery_icon(pct,charging,True); self.tray.setIcon(icon); self.setWindowIcon(icon)
        eta=human_eta(d.get("eta_minutes"))
        self.tray.setToolTip(f"Pi-Batt — {pct}% • {mode}\nETA: {eta}\nBattery: {d.get('battery_voltage_mv',0)/1000:.2f} V\nInput: {d.get('vbus_power_mw',0)/1000:.1f} W")

        vbus=bool(d.get("vbus_powered_stable",d.get("vbus_powered",False)))
        if self.prev_vbus is not None and vbus != self.prev_vbus:
            self.tray.showMessage("Pi-Batt", "External power restored" if vbus else f"External power lost — battery {pct}%", QSystemTrayIcon.Information, 5000)
        self.prev_vbus=vbus
        warning=d.get("warning_level","normal")
        if warning != self.prev_warning and warning in ("warning","critical") and not charging:
            self.tray.showMessage("Pi-Batt", f"Battery {warning}: {pct}% remaining", QSystemTrayIcon.Warning, 6000)
        self.prev_warning=warning

        self.diag_labels["connected"].setText("Connected")
        self.diag_labels["firmware"].setText("V"+str(d.get("software_version","—")))
        self.diag_labels["bq"].setText("OK" if d.get("bq4050_ok") else "ERROR")
        vbus_now=bool(d.get("vbus_powered_stable", d.get("vbus_powered", False)))
        if d.get("ip2368_ok"):
            self.diag_labels["ip"].setText("Active")
        elif not vbus_now:
            self.diag_labels["ip"].setText("Idle (battery mode)")
        else:
            self.diag_labels["ip"].setText("Check controller")
        self.diag_labels["auto"].setText("Enabled" if d.get("auto_start_on_power") else "Disabled")
        self.diag_labels["charge"].setText(d.get("charge_state","—"))
        self.diag_labels["id"].setText(hex(d.get("id",0)))
        self.last=d

    def _history_seconds(self):
        return [86400,7*86400,30*86400,90*86400][self.range.currentIndex()]

    def refresh_history(self):
        if not DB_PATH.exists(): return
        metric=self.series.currentText()
        col,scale,title,ymin,ymax={
            "Battery %":("battery_percent",1,"Battery %",0,100),
            "Battery voltage":("battery_voltage_mv",0.001,"Battery voltage (V)",12,17),
            "Battery current":("battery_current_ma",0.001,"Battery current (A)",-6,6),
            "Battery power":(None,1,"Battery power (W)",-80,80),
            "Input power":("vbus_power_mw",0.001,"USB-C input power (W)",0,45),
            "Cell delta":("cell_delta_mv",1,"Cell imbalance (mV)",0,150),
        }[metric]
        try:
            con=sqlite3.connect(f"file:{DB_PATH}?mode=ro",uri=True)
            cutoff=int(time.time())-self._history_seconds()
            if metric == "Battery power":
                raw=con.execute("SELECT ts,battery_voltage_mv,battery_current_ma FROM samples WHERE ts>=? ORDER BY ts",(cutoff,)).fetchall()
                rows=[(ts,(v*i)/1000000.0) for ts,v,i in raw if v is not None and i is not None]
                scale=1
            else:
                rows=con.execute(f"SELECT ts,{col} FROM samples WHERE ts>=? ORDER BY ts",(cutoff,)).fetchall()
            con.close()
            if len(rows)>700:
                step=math.ceil(len(rows)/700); rows=rows[::step]
            pts=[(float(x),float(y)*scale) for x,y in rows if y is not None]
            if pts and metric == "Battery power":
                vals=[y for _,y in pts]; pad=max(1.0,(max(vals)-min(vals))*0.15); ymin=min(vals)-pad; ymax=max(vals)+pad
            elif pts and metric not in ("Battery %","Battery voltage","Battery current","Input power","Cell delta"):
                vals=[y for _,y in pts]; ymin,ymax=min(vals),max(vals)
            self.chart.set_data(pts,ymin,ymax,title)
        except Exception:
            pass

    def refresh_events(self):
        if not DB_PATH.exists(): return
        try:
            con=sqlite3.connect(f"file:{DB_PATH}?mode=ro",uri=True)
            rows=con.execute("SELECT ts,event_type,details FROM events ORDER BY ts DESC LIMIT 40").fetchall(); con.close()
            self.events.setRowCount(len(rows))
            for r,(ts,typ,details) in enumerate(rows):
                vals=[time.strftime("%Y-%m-%d %H:%M:%S",time.localtime(ts)),typ,details or ""]
                for c,v in enumerate(vals): self.events.setItem(r,c,QTableWidgetItem(str(v)))
            ev=con=None
            con=sqlite3.connect(f"file:{DB_PATH}?mode=ro",uri=True)
            ev=con.execute("SELECT ts,event_type FROM events WHERE event_type IN ('mains_lost','mains_restored') ORDER BY ts").fetchall(); con.close()
            now=int(time.time()); outages=[]; open_start=None
            for ts,typ in ev:
                if typ=='mains_lost': open_start=ts
                elif typ=='mains_restored' and open_start is not None:
                    outages.append((open_start,ts)); open_start=None
            count24=sum(1 for a,b in outages if a>=now-86400) + (1 if open_start and open_start>=now-86400 else 0)
            durations=[b-a for a,b in outages if b>=now-7*86400]
            if open_start and open_start>=now-7*86400: durations.append(now-open_start)
            longest=max(durations) if durations else 0
            self.diag_labels['outages24'].setText(str(count24))
            self.diag_labels['longest7'].setText(human_eta(longest//60) if longest else '—')
            self.diag_labels['current_outage'].setText(human_eta((now-open_start)//60) if open_start else 'No')
        except Exception:
            pass

    def closeEvent(self,event):
        event.ignore(); self.hide()

class Tray(QSystemTrayIcon):
    def __init__(self, app):
        super().__init__(make_battery_icon(0,False,False), app)
        from PyQt5.QtWidgets import QMenu, QAction
        menu=QMenu(); show=QAction("Open Pi-Batt",menu); quitact=QAction("Quit tray app",menu)
        menu.addAction(show); menu.addSeparator(); menu.addAction(quitact); self.setContextMenu(menu)
        self.window=MainWindow(self)
        show.triggered.connect(self.open); quitact.triggered.connect(app.quit); self.activated.connect(self.clicked)
        self.setToolTip(f"Pi-Batt v{APP_VERSION} starting…"); self.show()
    def open(self):
        self.window.show()
    def clicked(self,reason):
        if reason in (QSystemTrayIcon.Trigger,QSystemTrayIcon.DoubleClick): self.open()

def main():
    app=QApplication(sys.argv); app.setApplicationName("Pi-Batt"); app.setQuitOnLastWindowClosed(False); apply_app_style(app)
    runtime=os.environ.get("XDG_RUNTIME_DIR") or "/tmp"
    lock=QLockFile(os.path.join(runtime, f"pi-batt-{os.getuid()}.lock")); lock.setStaleLockTime(0)
    if not lock.tryLock(100):
        return 0
    app._pi_batt_lock=lock
    tray=Tray(app)
    # Show the window on first run / manual launch; autostart can pass --tray.
    if "--tray" not in sys.argv: tray.open()
    sys.exit(app.exec_())

if __name__ == "__main__": main()
