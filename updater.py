#!/usr/bin/env python3
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

APP_NAME = "Pi-Batt"
GITHUB_REPO = "peperonikiller/Pi-Batt"
API_BASE = f"https://api.github.com/repos/{GITHUB_REPO}"
INSTALL_DIR = Path("/opt/pi-batt")
CONFIG_PATH = Path("/etc/pi-batt/config.json")
STATE_DIR = Path("/var/lib/pi-batt")
RUN_DIR = Path("/run/pi-batt")
UPDATE_STATUS = RUN_DIR / "update-status.json"
BACKUP_DIR = STATE_DIR / "backups"
USER_AGENT = "Pi-Batt-Updater/1.0"


def write_status(state, message, **extra):
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    data = {"state": state, "message": message, "timestamp": int(time.time()), **extra}
    tmp = UPDATE_STATUS.with_suffix(".tmp")
    with tmp.open("w") as f:
        json.dump(data, f, indent=2)
    os.chmod(tmp, 0o644)
    os.replace(tmp, UPDATE_STATUS)


def http_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.load(r)


def download(url, dest):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/octet-stream"})
    with urllib.request.urlopen(req, timeout=60) as r, dest.open("wb") as out:
        shutil.copyfileobj(r, out)


def version_tuple(value):
    s = str(value).strip().lstrip("vV")
    core = s.split("-", 1)[0]
    parts = core.split(".")
    try:
        return tuple(int(p) for p in parts)
    except ValueError:
        return (0,)


def current_version():
    try:
        return (INSTALL_DIR / "VERSION").read_text().strip()
    except Exception:
        return "0.0.0"


def latest_release():
    data = http_json(f"{API_BASE}/releases/latest")
    return {
        "tag": data.get("tag_name", ""),
        "version": data.get("tag_name", "").lstrip("vV"),
        "name": data.get("name") or data.get("tag_name", ""),
        "html_url": data.get("html_url", ""),
        "published_at": data.get("published_at", ""),
        "body": data.get("body") or "",
        "assets": data.get("assets") or [],
    }


def find_assets(release):
    tag = release["tag"]
    version = tag.lstrip("vV")
    zip_name = f"Pi-Batt-v{version}.zip"
    sha_name = zip_name + ".sha256"
    zip_asset = sha_asset = None
    for a in release.get("assets", []):
        if a.get("name") == zip_name:
            zip_asset = a
        elif a.get("name") == sha_name:
            sha_asset = a
    if not zip_asset:
        raise RuntimeError(f"Release {tag} is missing required asset {zip_name}")
    if not sha_asset:
        raise RuntimeError(f"Release {tag} is missing required checksum {sha_name}")
    return zip_asset, sha_asset


def verify_sha256(zip_path, sha_path):
    expected = sha_path.read_text().strip().split()[0].lower()
    h = hashlib.sha256()
    with zip_path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    actual = h.hexdigest().lower()
    if actual != expected:
        raise RuntimeError(f"SHA256 mismatch: expected {expected}, got {actual}")
    return actual


def find_payload(extract_dir):
    candidates = [extract_dir]
    candidates.extend(p for p in extract_dir.rglob("manifest.json") if p.is_file())
    if candidates and candidates[0] == extract_dir:
        manifest = extract_dir / "manifest.json"
        if manifest.exists():
            return extract_dir
    for manifest in candidates[1:]:
        return manifest.parent
    raise RuntimeError("Release archive does not contain manifest.json")


def validate_payload(payload, expected_version):
    manifest = json.loads((payload / "manifest.json").read_text())
    if manifest.get("product") != APP_NAME:
        raise RuntimeError("Release manifest product mismatch")
    if str(manifest.get("version")) != str(expected_version):
        raise RuntimeError(f"Release manifest version mismatch: {manifest.get('version')} != {expected_version}")
    required = [
        "VERSION", "daemon.py", "gui.py", "pibatt_hw.py", "pibattctl.py", "updater.py",
        "pi-batt-launch", "pi-batt.service", "pi-batt.desktop", "pi-batt-app.desktop", "config.json"
    ]
    missing = [name for name in required if not (payload / name).exists()]
    if missing:
        raise RuntimeError("Release is missing: " + ", ".join(missing))
    for py in ["daemon.py", "gui.py", "pibatt_hw.py", "pibattctl.py", "updater.py"]:
        subprocess.run([sys.executable, "-m", "py_compile", str(payload / py)], check=True)
    return manifest


def merge_config(default_path):
    defaults = json.loads(default_path.read_text())
    existing = {}
    if CONFIG_PATH.exists():
        try:
            existing = json.loads(CONFIG_PATH.read_text())
        except Exception:
            existing = {}
    merged = dict(defaults)
    merged.update(existing)
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(merged, indent=2) + "\n")
    os.chmod(CONFIG_PATH, 0o664)


def prune_backups(keep=3):
    if not BACKUP_DIR.exists():
        return
    backups=sorted((p for p in BACKUP_DIR.iterdir() if p.is_dir()), key=lambda p:p.stat().st_mtime, reverse=True)
    for old in backups[keep:]:
        shutil.rmtree(old, ignore_errors=True)


def apply_payload(payload, version):
    if os.geteuid() != 0:
        raise PermissionError("Update installation must run as root")

    write_status("installing", f"Installing Pi-Batt v{version}", version=version)
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    backup = None
    if INSTALL_DIR.exists():
        old_ver = current_version()
        stamp = time.strftime("%Y%m%d-%H%M%S")
        backup = BACKUP_DIR / f"v{old_ver}-{stamp}"
        shutil.copytree(INSTALL_DIR, backup, dirs_exist_ok=True)
        prune_backups(keep=3)

    try:
        INSTALL_DIR.mkdir(parents=True, exist_ok=True)
        for name in ["daemon.py", "gui.py", "pibatt_hw.py", "pibattctl.py", "updater.py", "VERSION", "manifest.json"]:
            shutil.copy2(payload / name, INSTALL_DIR / name)
        for py in INSTALL_DIR.glob("*.py"):
            os.chmod(py, 0o755)
    except Exception:
        if backup and backup.exists():
            shutil.rmtree(INSTALL_DIR, ignore_errors=True)
            shutil.copytree(backup, INSTALL_DIR, dirs_exist_ok=True)
        raise

    shutil.copy2(payload / "pi-batt-launch", "/usr/local/bin/pi-batt")
    os.chmod("/usr/local/bin/pi-batt", 0o755)
    try:
        Path("/usr/local/bin/pi-battctl").unlink()
    except FileNotFoundError:
        pass
    os.symlink("/opt/pi-batt/pibattctl.py", "/usr/local/bin/pi-battctl")

    shutil.copy2(payload / "pi-batt.service", "/etc/systemd/system/pi-batt.service")
    Path("/usr/share/applications").mkdir(parents=True, exist_ok=True)
    Path("/etc/xdg/autostart").mkdir(parents=True, exist_ok=True)
    shutil.copy2(payload / "pi-batt-app.desktop", "/usr/share/applications/pi-batt.desktop")
    shutil.copy2(payload / "pi-batt.desktop", "/etc/xdg/autostart/pi-batt.desktop")
    merge_config(payload / "config.json")

    subprocess.run(["/usr/bin/systemctl", "daemon-reload"], check=True)
    subprocess.run(["/usr/bin/systemctl", "enable", "pi-batt.service"], check=False)
    subprocess.run(["/usr/bin/systemctl", "restart", "pi-batt.service"], check=False)
    write_status("installed", f"Pi-Batt v{version} installed successfully", version=version, restart_gui=True)


def fetch_release_to_temp(release):
    zip_asset, sha_asset = find_assets(release)
    td = tempfile.TemporaryDirectory(prefix="pi-batt-update-")
    temp = Path(td.name)
    zip_path = temp / zip_asset["name"]
    sha_path = temp / sha_asset["name"]
    write_status("downloading", f"Downloading {zip_asset['name']}", version=release["version"])
    download(zip_asset["browser_download_url"], zip_path)
    download(sha_asset["browser_download_url"], sha_path)
    digest = verify_sha256(zip_path, sha_path)
    extract = temp / "extract"
    extract.mkdir()
    with zipfile.ZipFile(zip_path) as z:
        z.extractall(extract)
    payload = find_payload(extract)
    validate_payload(payload, release["version"])
    return td, payload, digest


def install_latest(force=False):
    release = latest_release()
    cur = current_version()
    if not force and version_tuple(release["version"]) <= version_tuple(cur):
        write_status("up_to_date", f"Pi-Batt v{cur} is already current", version=cur)
        return 0
    td, payload, digest = fetch_release_to_temp(release)
    try:
        apply_payload(payload, release["version"])
    finally:
        td.cleanup()
    return 0


def verify_latest():
    release = latest_release()
    td, _payload, digest = fetch_release_to_temp(release)
    try:
        write_status("verified", f"Release v{release['version']} downloaded and verified", version=release["version"], sha256=digest)
    finally:
        td.cleanup()
    return 0


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--check", action="store_true")
    p.add_argument("--install-latest", action="store_true")
    p.add_argument("--force", action="store_true")
    p.add_argument("--verify-latest", action="store_true")
    args = p.parse_args()
    try:
        if args.check:
            r = latest_release()
            r["current_version"] = current_version()
            r["update_available"] = version_tuple(r["version"]) > version_tuple(r["current_version"])
            print(json.dumps(r, indent=2))
            return 0
        if args.verify_latest:
            return verify_latest()
        if args.install_latest:
            return install_latest(args.force)
        p.error("choose --check, --verify-latest, or --install-latest")
    except urllib.error.HTTPError as e:
        msg = f"GitHub HTTP error {e.code}: {e.reason}"
        try: write_status("error", msg)
        except Exception: pass
        print(msg, file=sys.stderr)
        return 2
    except Exception as e:
        try: write_status("error", str(e))
        except Exception: pass
        print(f"Update failed: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
