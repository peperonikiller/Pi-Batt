#!/bin/bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"
VERSION="$(tr -d '[:space:]' < VERSION)"
NAME="Pi-Batt-v${VERSION}"
DIST="$ROOT/dist"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
mkdir -p "$DIST" "$TMP/$NAME"
cp README.md CHANGELOG.md VERSION manifest.json config.json daemon.py gui.py pibatt_hw.py pibattctl.py updater.py install.sh uninstall.sh pi-batt-launch pi-batt.service pi-batt.desktop pi-batt-app.desktop "$TMP/$NAME/"
(cd "$TMP" && zip -qr "$DIST/$NAME.zip" "$NAME")
(cd "$DIST" && sha256sum "$NAME.zip" > "$NAME.zip.sha256")
echo "Created:"
echo "  $DIST/$NAME.zip"
echo "  $DIST/$NAME.zip.sha256"
