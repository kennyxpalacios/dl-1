"""
app.py — dl-1 as a mac app window.

dl-1.app (built by make_app.py) boots into this. it starts the server in-process
unless one is already running on the port, then opens a native window on it.
close the window and everything shuts down. `python app.py` does the same thing
from a terminal.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import threading
import time
import urllib.request
import webbrowser
from pathlib import Path

BASE = Path(__file__).resolve().parent
HOST = os.environ.get("DL1_HOST", "127.0.0.1")
PORT = int(os.environ.get("DL1_PORT", "3300"))
URL = f"http://{HOST}:{PORT}"
SAVE_DIR = Path(os.environ.get("DL1_SAVE_DIR", Path.home() / "Downloads"))


def server_up(timeout: float = 0.5) -> bool:
    try:
        with urllib.request.urlopen(f"{URL}/api/health", timeout=timeout) as res:
            return res.status == 200
    except Exception:
        return False


def start_server() -> None:
    sys.path.insert(0, str(BASE))
    import uvicorn
    import server
    config = uvicorn.Config(server.app, host=HOST, port=PORT, log_level="info")
    threading.Thread(target=uvicorn.Server(config).run, name="dl1-server", daemon=True).start()
    for _ in range(150):
        if server_up(0.3):
            return
        time.sleep(0.1)
    raise SystemExit("dl-1: the server didn't come up")


class Api:
    """reachable from the page as window.pywebview.api.<method>(...)"""

    def save(self, job_id: str, name: str) -> dict:
        try:
            SAVE_DIR.mkdir(parents=True, exist_ok=True)
            dest = _unique(SAVE_DIR / _safe_name(name))
            with urllib.request.urlopen(f"{URL}/api/jobs/{job_id}/file") as res, open(dest, "wb") as out:
                shutil.copyfileobj(res, out)
            subprocess.Popen(["open", "-R", str(dest)])          # reveal in finder
            return {"ok": True, "path": str(dest).replace(str(Path.home()), "~", 1)}
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": f"couldn't save // {exc}"}

    def open_url(self, url: str) -> dict:
        if url.startswith(("http://", "https://")):
            webbrowser.open(url)
        return {"ok": True}


def _safe_name(name: str) -> str:
    return name.replace("/", "-").replace(":", "-").strip() or "download"


def _unique(path: Path) -> Path:
    if not path.exists():
        return path
    for i in range(2, 1000):
        candidate = path.with_name(f"{path.stem} ({i}){path.suffix}")
        if not candidate.exists():
            return candidate
    return path


def _polish_dock() -> None:
    """when launched as plain `python app.py`: our icon and name instead of python's."""
    try:
        from AppKit import NSApplication, NSImage
        from Foundation import NSBundle
        icon = BASE / "launcher" / "dl-1.icns"
        app = NSApplication.sharedApplication()
        if icon.exists():
            app.setApplicationIconImage_(NSImage.alloc().initWithContentsOfFile_(str(icon)))
        info = NSBundle.mainBundle().infoDictionary()
        if info is not None and not info.get("CFBundleName"):
            info["CFBundleName"] = "dl-1"
    except Exception:  # noqa: BLE001 — cosmetics only
        pass


def main() -> None:
    import webview
    if not server_up():
        start_server()
    _polish_dock()
    webview.create_window(
        "dl-1", URL, js_api=Api(),
        width=1240, height=860, min_size=(420, 640),
        background_color="#f4f4f4", text_select=True,
    )
    webview.start()


if __name__ == "__main__":
    main()
