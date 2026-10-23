"""
python imports this module by itself at startup when it is on PYTHONPATH.
dl-1.app sets that up (see make_app.py): the bundle's executable is a plain
python symlink, and this file is what turns it into the app. it only acts when
DL1_APP_LAUNCH=1, so it never interferes with any other python run.
"""
import os
import sys

if os.environ.get("DL1_APP_LAUNCH") == "1":
    import site

    project = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    log = open(os.path.join(project, "app.log"), "a", buffering=1)   # finder gives us no console
    sys.stdout = sys.stderr = log
    version = f"python{sys.version_info.major}.{sys.version_info.minor}"
    site.addsitedir(os.path.join(project, ".venv", "lib", version, "site-packages"))
    sys.path.insert(0, project)
    try:
        import app
        app.main()
    except BaseException:  # noqa: BLE001 — whatever happens, land in the log
        import traceback
        traceback.print_exc()
    finally:
        os._exit(0)
