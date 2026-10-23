"""
make_app.py — builds dl-1.app and puts it in /Applications and the dock.

    .venv/bin/python make_app.py               build + install + dock
    .venv/bin/python make_app.py --no-dock     build + install
    .venv/bin/python make_app.py --build-only  just write dist/dl-1.app
    .venv/bin/python make_app.py --share       build a self-contained dl-1.app for other macs → dist/dl-1-mac.zip

the app is a thin shell: a symlink to this folder's python inside the bundle,
plus an Info.plist that points python at launcher/sitecustomize.py, which boots
app.py. nothing is copied, so the app always runs the code in this folder.
move or rename the folder and run this again.
"""
from __future__ import annotations

import os
import plistlib
import shutil
import subprocess
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parent
LAUNCHER = PROJECT / "launcher"
DIST = PROJECT / "dist"
APP_NAME = "dl-1"
BUNDLE_ID = "studio.palace.dl1"
PYTHON = Path(sys.base_prefix) / "bin" / f"python{sys.version_info.major}.{sys.version_info.minor}"
LSREGISTER = ("/System/Library/Frameworks/CoreServices.framework/Frameworks/"
              "LaunchServices.framework/Support/lsregister")

OFF_WHITE = (0.957, 0.957, 0.957)
ORANGE = (1.0, 0.2, 0.0)


def say(msg: str) -> None:
    print(f"[dl-1] {msg}")


# ---------------------------------------------------------------------------
# icon: off-white tile, one orange square, "dl–1" underneath — drawn with appkit
# ---------------------------------------------------------------------------
def render_icon_png(path: Path, size: int = 1024) -> None:
    from AppKit import (NSBezierPath, NSBitmapImageRep, NSCalibratedRGBColorSpace, NSColor, NSFont,
                        NSFontAttributeName, NSForegroundColorAttributeName, NSGraphicsContext, NSString)
    from Foundation import NSMakeRect

    rep = NSBitmapImageRep.alloc().initWithBitmapDataPlanes_pixelsWide_pixelsHigh_bitsPerSample_samplesPerPixel_hasAlpha_isPlanar_colorSpaceName_bytesPerRow_bitsPerPixel_(
        None, size, size, 8, 4, True, False, NSCalibratedRGBColorSpace, 0, 0)
    NSGraphicsContext.saveGraphicsState()
    NSGraphicsContext.setCurrentContext_(NSGraphicsContext.graphicsContextWithBitmapImageRep_(rep))

    inset = size * 100 / 1024                       # apple's icon grid: tile is 824/1024 of the canvas
    tile = size - 2 * inset
    radius = tile * 0.2237
    tile_rect = NSMakeRect(inset, inset, tile, tile)
    NSColor.colorWithSRGBRed_green_blue_alpha_(*OFF_WHITE, 1).setFill()
    NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(tile_rect, radius, radius).fill()

    # hairline frame just inside the tile, like the panel border
    NSColor.blackColor().setStroke()
    frame = NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(
        NSMakeRect(inset + tile * 0.05, inset + tile * 0.05, tile * 0.9, tile * 0.9), radius * 0.78, radius * 0.78)
    frame.setLineWidth_(max(2.0, size / 256))
    frame.stroke()

    square = tile * 0.40
    NSColor.colorWithSRGBRed_green_blue_alpha_(*ORANGE, 1).setFill()
    NSBezierPath.fillRect_(NSMakeRect(inset + (tile - square) / 2, inset + tile * 0.42, square, square))

    font = NSFont.fontWithName_size_("HelveticaNeue-Medium", tile * 0.17) or NSFont.boldSystemFontOfSize_(tile * 0.17)
    attrs = {NSFontAttributeName: font, NSForegroundColorAttributeName: NSColor.blackColor()}
    label = NSString.stringWithString_("dl–1")
    width, _height = label.sizeWithAttributes_(attrs)
    label.drawAtPoint_withAttributes_((inset + (tile - width) / 2, inset + tile * 0.17), attrs)

    NSGraphicsContext.restoreGraphicsState()
    png_type = 4  # NSBitmapImageFileTypePNG
    rep.representationUsingType_properties_(png_type, None).writeToFile_atomically_(str(path), True)


def build_icns(png: Path, icns: Path) -> None:
    iconset = icns.with_suffix(".iconset")
    shutil.rmtree(iconset, ignore_errors=True)
    iconset.mkdir()
    for base in (16, 32, 128, 256, 512):
        for scale in (1, 2):
            px = base * scale
            name = f"icon_{base}x{base}{'@2x' if scale == 2 else ''}.png"
            subprocess.run(["sips", "-z", str(px), str(px), str(png), "--out", str(iconset / name)],
                           check=True, capture_output=True)
    subprocess.run(["iconutil", "-c", "icns", str(iconset), "-o", str(icns)], check=True)
    shutil.rmtree(iconset, ignore_errors=True)


# ---------------------------------------------------------------------------
# bundle
# ---------------------------------------------------------------------------
def build_bundle(app_dir: Path, icns: Path) -> None:
    if app_dir.exists():
        shutil.rmtree(app_dir)
    macos = app_dir / "Contents" / "MacOS"
    resources = app_dir / "Contents" / "Resources"
    macos.mkdir(parents=True)
    resources.mkdir(parents=True)
    os.symlink(PYTHON, macos / APP_NAME)
    shutil.copy2(icns, resources / f"{APP_NAME}.icns")
    info = _info_plist({"DL1_APP_LAUNCH": "1", "PYTHONPATH": str(LAUNCHER),
                        "PYTHONNOUSERSITE": "1", "PYTHONUNBUFFERED": "1"})
    with open(app_dir / "Contents" / "Info.plist", "wb") as fh:
        plistlib.dump(info, fh)
    (app_dir / "Contents" / "PkgInfo").write_text("APPL????")


def install(app_dir: Path) -> Path:
    root = Path("/Applications") if os.access("/Applications", os.W_OK) else Path.home() / "Applications"
    root.mkdir(parents=True, exist_ok=True)
    target = root / app_dir.name
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(app_dir, target, symlinks=True)
    subprocess.run([LSREGISTER, "-f", str(target)], check=False, capture_output=True)
    subprocess.run(["touch", str(target)], check=False)
    return target


def add_to_dock(target: Path) -> None:
    exported = subprocess.run(["defaults", "export", "com.apple.dock", "-"], capture_output=True).stdout
    prefs = plistlib.loads(exported) if exported else {}
    for item in prefs.get("persistent-apps", []):
        url = item.get("tile-data", {}).get("file-data", {}).get("_CFURLString", "")
        if url.rstrip("/").endswith(target.name):
            say("already in the dock")
            return
    entry = ("<dict><key>tile-data</key><dict><key>file-data</key><dict>"
             f"<key>_CFURLString</key><string>{target}</string>"
             "<key>_CFURLStringType</key><integer>0</integer>"
             "</dict></dict></dict>")
    subprocess.run(["defaults", "write", "com.apple.dock", "persistent-apps", "-array-add", entry], check=True)
    subprocess.run(["killall", "Dock"], check=False)
    say("added to the dock")


# ---------------------------------------------------------------------------
# share build: everything inside the bundle, no path points back to this folder
# ---------------------------------------------------------------------------
PORTABLE_BOOT = '''"""
dl-1 boot shim. the app bundle's python is launched with no script, and python
imports this file by itself at startup — that is how the app starts. it only
fires inside the bundle (DL1_PORTABLE=1, no arguments), never for other runs.
"""
import os
import sys

if os.environ.get("DL1_PORTABLE") == "1" and sys.argv == [""] and not os.environ.get("DL1_NO_APP"):
    contents = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
    resources = os.path.join(contents, "Resources")
    home = os.path.expanduser("~")
    logs = os.path.join(home, "Library", "Logs")
    os.makedirs(logs, exist_ok=True)
    sys.stdout = sys.stderr = open(os.path.join(logs, "dl-1.log"), "a", buffering=1)
    cache = os.path.join(home, "Library", "Caches", "dl-1")
    os.makedirs(cache, exist_ok=True)
    os.environ.setdefault("DL1_DOWNLOAD_DIR", os.path.join(cache, "downloads"))
    sys.path.insert(0, os.path.join(resources, "app"))
    try:
        import app
        app.main()
    except BaseException:  # noqa: BLE001
        import traceback
        traceback.print_exc()
    finally:
        os._exit(0)
'''

PY_TRIM = ("test", "tests", "idlelib", "tkinter", "turtledemo", "ensurepip", "lib2to3", "PyObjCTest",
           "tcl9.0", "tk9.0", "tcl8", "tk8", "itcl4.3.0", "thread3.0.1", "__pycache__")
PY_TRIM_FILES = ("libpython*.a", "libpython*.dylib", "libtcl*", "libtk*", "*.pyi")


def _mach_o_files(root: Path):
    for path in root.rglob("*"):
        if path.is_file() and not path.is_symlink() and (path.suffix in (".so", ".dylib") or os.access(path, os.X_OK)):
            with open(path, "rb") as fh:
                magic = fh.read(4)
            if magic in (b"\xcf\xfa\xed\xfe", b"\xca\xfe\xba\xbe", b"\xce\xfa\xed\xfe"):
                yield path


def build_portable(app_dir: Path, icns: Path) -> None:
    """
    layout (the interpreter itself is the app's executable, so the bundle signs cleanly):
      Contents/MacOS/dl-1            python3.12, renamed
      Contents/lib/python3.12/       stdlib + lib-dynload + site-packages (packages, ffmpeg, boot shim)
      Contents/Resources/app/        dl-1's own code + static files
    """
    version = f"python{sys.version_info.major}.{sys.version_info.minor}"
    if app_dir.exists():
        shutil.rmtree(app_dir)
    contents = app_dir / "Contents"
    macos, resources, lib = contents / "MacOS", contents / "Resources", contents / "lib" / version
    macos.mkdir(parents=True)
    resources.mkdir()
    shutil.copy2(icns, resources / f"{APP_NAME}.icns")

    say("copying python (trimmed)")
    py_root = Path(sys.base_prefix)
    shutil.copy2(py_root / "bin" / version, macos / APP_NAME)
    shutil.copytree(py_root / "lib" / version, lib, symlinks=True,
                    ignore=shutil.ignore_patterns(*PY_TRIM, *PY_TRIM_FILES))
    for dylib in (py_root / "lib").glob("*.dylib"):                 # openssl and friends, if any
        if not any(dylib.match(pattern) for pattern in PY_TRIM_FILES):
            shutil.copy2(dylib, contents / "lib" / dylib.name)

    say("copying packages")
    site_src = Path(sys.prefix) / "lib" / version / "site-packages"
    shutil.copytree(site_src, lib / "site-packages", symlinks=True, dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns(*PY_TRIM))
    (lib / "site-packages" / "sitecustomize.py").write_text(PORTABLE_BOOT)

    say("copying the app")
    app_code = resources / "app"
    app_code.mkdir()
    for name in ("app.py", "server.py", "jobs.py", "downloader.py"):
        shutil.copy2(PROJECT / name, app_code / name)
    shutil.copytree(PROJECT / "static", app_code / "static")

    info = _info_plist({"DL1_PORTABLE": "1", "PYTHONDONTWRITEBYTECODE": "1",
                        "PYTHONNOUSERSITE": "1", "PYTHONUNBUFFERED": "1"})
    with open(contents / "Info.plist", "wb") as fh:
        plistlib.dump(info, fh)
    (contents / "PkgInfo").write_text("APPL????")

    say("precompiling inside the bundle")
    subprocess.run([str(macos / APP_NAME), "-m", "compileall", "-q", "-j", "0", str(lib)],
                   env={**os.environ, "DL1_NO_APP": "1"}, check=False, capture_output=True)

    say("signing (ad hoc)")
    for binary in _mach_o_files(contents / "lib"):
        subprocess.run(["codesign", "--force", "--sign", "-", str(binary)], check=False, capture_output=True)
    result = subprocess.run(["codesign", "--force", "--sign", "-", "--identifier", BUNDLE_ID, str(app_dir)],
                            capture_output=True, text=True)
    if result.returncode != 0:
        say(f"signing warning: {result.stderr.strip()}")


def _info_plist(env: dict) -> dict:
    return {
        "CFBundleName": APP_NAME,
        "CFBundleDisplayName": APP_NAME,
        "CFBundleIdentifier": BUNDLE_ID,
        "CFBundleVersion": "1.0",
        "CFBundleShortVersionString": "1.0",
        "CFBundlePackageType": "APPL",
        "CFBundleExecutable": APP_NAME,
        "CFBundleIconFile": APP_NAME,
        "CFBundleInfoDictionaryVersion": "6.0",
        "LSMinimumSystemVersion": "11.0",
        "LSApplicationCategoryType": "public.app-category.utilities",
        "NSHighResolutionCapable": True,
        "NSHumanReadableCopyright": "palace studios",
        "LSEnvironment": env,
    }


def zip_app(app_dir: Path, zip_path: Path) -> None:
    zip_path.unlink(missing_ok=True)
    subprocess.run(["ditto", "-c", "-k", "--sequesterRsrc", "--keepParent", str(app_dir), str(zip_path)], check=True)


def zip_source(zip_path: Path) -> None:
    """the folder without the heavy bits, for intel macs or anyone who wants the code."""
    zip_path.unlink(missing_ok=True)
    names = ["run.sh", "requirements.txt", "README.md", "CLAUDE.md", ".gitignore", "screenshot.png",
             "app.py", "server.py", "jobs.py", "downloader.py", "make_app.py", "static", "launcher/sitecustomize.py"]
    subprocess.run(["zip", "-q", "-r", str(zip_path), *names, "-x", "*/__pycache__/*", "*.pyc"],
                   cwd=PROJECT, check=True)


# ---------------------------------------------------------------------------
def main(argv: list[str]) -> None:
    try:
        import webview  # noqa: F401
    except ImportError:
        sys.exit("[dl-1] pywebview is missing — run `bash run.sh --setup` first")
    if not PYTHON.exists():
        sys.exit(f"[dl-1] can't find the python binary at {PYTHON}")

    say("precompiling python packages (makes launch fast)")
    site_packages = Path(sys.prefix) / "lib" / f"python{sys.version_info.major}.{sys.version_info.minor}" / "site-packages"
    subprocess.run([sys.executable, "-m", "compileall", "-q", "-j", "0", str(site_packages), str(PROJECT / "launcher"),
                    *(str(PROJECT / f) for f in ("app.py", "server.py", "jobs.py", "downloader.py"))],
                   check=False, capture_output=True)

    LAUNCHER.mkdir(exist_ok=True)
    png, icns = LAUNCHER / "icon.png", LAUNCHER / f"{APP_NAME}.icns"
    say("rendering icon")
    render_icon_png(png)
    build_icns(png, icns)

    if "--share" in argv:
        share_dir = DIST / "share"
        share_dir.mkdir(parents=True, exist_ok=True)
        app_dir = share_dir / f"{APP_NAME}.app"
        say(f"building a self-contained {app_dir.relative_to(PROJECT)}")
        build_portable(app_dir, icns)
        zip_app(app_dir, DIST / f"{APP_NAME}-mac.zip")
        zip_source(DIST / f"{APP_NAME}-source.zip")
        size = DIST.joinpath(f"{APP_NAME}-mac.zip").stat().st_size / 1e6
        say(f"done → dist/{APP_NAME}-mac.zip ({size:.0f} mb, apple silicon) + dist/{APP_NAME}-source.zip (any mac, needs terminal)")
        return

    app_dir = DIST / f"{APP_NAME}.app"
    say(f"building {app_dir.relative_to(PROJECT)}")
    build_bundle(app_dir, icns)
    if "--build-only" in argv:
        say("done (not installed)")
        return

    target = install(app_dir)
    say(f"installed → {target}")
    if "--no-dock" not in argv:
        add_to_dock(target)
    say("ready. click the dock icon, or open it from applications.")


if __name__ == "__main__":
    main(sys.argv[1:])
