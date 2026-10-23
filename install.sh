#!/usr/bin/env bash
# dl-1 // one-line install for apple silicon macs
#
#   curl -fsSL https://raw.githubusercontent.com/kennyxpalacios/dl-1/main/install.sh | bash
#
# downloads the latest dl-1-mac.zip from github releases, puts dl-1.app in your
# applications folder and opens it. files fetched with curl don't get macos's
# download quarantine flag, so there's no "open anyway" step. same zip as the
# releases page. read this file first if you like. it's short.
set -euo pipefail

say()  { printf '\033[1m[dl-1]\033[0m %s\n' "$*"; }
fail() { printf '\033[1m[dl-1]\033[0m %s\n' "$*" >&2; exit 1; }

[ "$(uname -s)" = "Darwin" ] || fail "this installer is for macs. everything else: see the readme."
[ "$(uname -m)" = "arm64" ]  || fail "this mac has an intel chip. the app zip is for apple silicon. use the from-source path: https://github.com/kennyxpalacios/dl-1/blob/main/docs/from-source.md"

URL="https://github.com/kennyxpalacios/dl-1/releases/latest/download/dl-1-mac.zip"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

say "downloading the latest release"
curl -fL --progress-bar -o "$TMP/dl-1-mac.zip" "$URL" || fail "download failed. check your connection and try again."

say "unzipping"
ditto -x -k "$TMP/dl-1-mac.zip" "$TMP/out"
APP="$(find "$TMP/out" -maxdepth 2 -name 'dl-1.app' -type d | head -n 1)"
[ -n "$APP" ] || fail "couldn't find dl-1.app in the zip."

DEST="/Applications"
[ -w "$DEST" ] || DEST="$HOME/Applications"
mkdir -p "$DEST"

if pgrep -x dl-1 >/dev/null 2>&1; then
  say "closing the copy that's running"
  osascript -e 'quit app "dl-1"' >/dev/null 2>&1 || true
  sleep 1
fi

rm -rf "$DEST/dl-1.app"
ditto "$APP" "$DEST/dl-1.app"
xattr -dr com.apple.quarantine "$DEST/dl-1.app" 2>/dev/null || true

say "installed // $DEST/dl-1.app"
open "$DEST/dl-1.app"
say "done. to keep it in the dock: right-click the icon, options, keep in dock."
