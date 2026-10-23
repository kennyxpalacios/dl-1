#!/usr/bin/env bash
# dl-1 // universal media downloader — one-shot setup + launch
#
#   bash run.sh            first run: set up, then start the server. later runs: just start.
#   bash run.sh --setup    set up only, don't start
#   bash run.sh --reset    wipe .venv/ and .tools/, set up again, start
#
# python 3.10+ is required (current yt-dlp needs it). if this machine has none,
# the script downloads `uv` and a standalone python INTO THIS FOLDER (.tools/).
# nothing is installed system-wide. delete .tools/ and .venv/ to undo everything.
set -euo pipefail
cd "$(dirname "$0")"

TOOLS="$PWD/.tools"
VENV="$PWD/.venv"
PY_WANT="3.12"
HOST="${DL1_HOST:-127.0.0.1}"
PORT="${DL1_PORT:-3300}"

say() { printf '\033[1m[dl-1]\033[0m %s\n' "$*"; }

find_python() {
  local c
  for c in python3.13 python3.12 python3.11 python3.10; do
    if command -v "$c" >/dev/null 2>&1; then command -v "$c"; return 0; fi
  done
  for c in /Library/Frameworks/Python.framework/Versions/3.1[0-9]/bin/python3; do
    if [ -x "$c" ]; then echo "$c"; return 0; fi
  done
  if command -v python3 >/dev/null 2>&1 \
     && python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' 2>/dev/null; then
    command -v python3; return 0
  fi
  return 1
}

ensure_uv() {
  if command -v uv >/dev/null 2>&1; then command -v uv; return 0; fi
  if [ -x "$TOOLS/uv" ]; then echo "$TOOLS/uv"; return 0; fi
  local arch os target
  arch="$(uname -m)"; os="$(uname -s)"
  case "$arch" in
    arm64|aarch64) arch="aarch64" ;;
    x86_64|amd64)  arch="x86_64" ;;
    *) say "unsupported cpu: $arch"; return 1 ;;
  esac
  case "$os" in
    Darwin) target="${arch}-apple-darwin" ;;
    Linux)  target="${arch}-unknown-linux-gnu" ;;
    *) say "unsupported os: $os"; return 1 ;;
  esac
  say "no python 3.10+ on this machine — fetching uv into .tools/ (github.com/astral-sh/uv)" >&2
  mkdir -p "$TOOLS"
  curl -fsSL "https://github.com/astral-sh/uv/releases/latest/download/uv-${target}.tar.gz" \
    | tar -xz -C "$TOOLS" --strip-components=1
  echo "$TOOLS/uv"
}

setup() {
  if [ -x "$VENV/bin/python" ] \
     && "$VENV/bin/python" -c 'import yt_dlp, fastapi, uvicorn, imageio_ffmpeg' 2>/dev/null; then
    say "environment ok // $("$VENV/bin/python" --version 2>&1) // yt-dlp $("$VENV/bin/python" -c 'import yt_dlp; print(yt_dlp.version.__version__)')"
    return 0
  fi
  local py
  if py="$(find_python)"; then
    say "using $py ($("$py" --version 2>&1))"
    "$py" -m venv "$VENV"
    "$VENV/bin/python" -m pip install --quiet --upgrade pip
    say "installing requirements"
    "$VENV/bin/python" -m pip install --quiet -r requirements.txt
  else
    local uv
    uv="$(ensure_uv)"
    export UV_PYTHON_INSTALL_DIR="$TOOLS/python"
    say "installing python $PY_WANT into .tools/ (standalone build, nothing system-wide)"
    "$uv" python install "$PY_WANT" --quiet
    "$uv" venv --quiet --python "$PY_WANT" "$VENV"
    say "installing requirements"
    "$uv" pip install --quiet --compile-bytecode --python "$VENV/bin/python" -r requirements.txt
  fi
  say "setup complete"
}

case "${1:-}" in
  --reset) rm -rf "$VENV" "$TOOLS"; setup ;;
  --setup) setup; exit 0 ;;
  *)       setup ;;
esac

say "running on http://$HOST:$PORT   (ctrl+c to stop)"
exec "$VENV/bin/python" -m uvicorn server:app --host "$HOST" --port "$PORT"
