# -*- mode: python ; coding: utf-8 -*-

import os
import sys
from pathlib import Path

_icon = Path("evelina/assets/logo.ico")
icon = str(_icon) if sys.platform == "win32" and _icon.is_file() else None
binaries = []
datas = []
hiddenimports = [
    "evelina",
    "evelina.db",
    "evelina.mariadb_conn",
    "evelina.distribution",
    "evelina.ui",
    "pymysql",
]
runtime_hooks = []
hooksconfig = {}

if sys.platform == "win32":
    _prefix_candidates = [
        os.environ.get("UCRT64_PREFIX"),
        os.environ.get("MSYSTEM_PREFIX"),
        r"C:\msys64\ucrt64",
    ]
    prefix = None
    for raw in _prefix_candidates:
        if not raw:
            continue
        candidate = Path(raw)
        if (candidate / "lib" / "girepository-1.0").is_dir():
            prefix = candidate
            break
    if prefix is None:
        prefix = Path(r"C:\msys64\ucrt64")
    binaries += [(str(path), ".") for path in (prefix / "bin").glob("*.dll")]
    datas += [
        (str(prefix / "lib" / "girepository-1.0"), os.path.join("lib", "girepository-1.0")),
        (str(prefix / "lib" / "gdk-pixbuf-2.0"), os.path.join("lib", "gdk-pixbuf-2.0")),
        (str(prefix / "share" / "glib-2.0" / "schemas"), os.path.join("share", "glib-2.0", "schemas")),
        (str(prefix / "share" / "icons"), os.path.join("share", "icons")),
    ]
    hiddenimports += [
        "gi",
        "gi.repository.Gtk",
        "gi.repository.Adw",
        "gi.repository.Gdk",
        "gi.repository.GdkPixbuf",
        "gi.repository.Gio",
        "gi.repository.GLib",
        "gi.repository.GObject",
        "gi.repository.Pango",
        "gi.repository.cairo",
        "cairo",
    ]
    hooksconfig = {
        "gi": {
            "module-versions": {
                "Gtk": "4.0",
                "Gdk": "4.0",
            },
        },
    }
    runtime_hooks.append("evelina/windows_runtime.py")
else:
    hiddenimports += [
        "gi",
        "gi.repository.Gtk",
        "gi.repository.Adw",
        "gi.repository.Gdk",
        "gi.repository.GdkPixbuf",
        "gi.repository.Gio",
        "gi.repository.GLib",
        "gi.repository.GObject",
        "gi.repository.Pango",
        "gi.repository.cairo",
        "cairo",
    ]
    hooksconfig = {
        "gi": {
            "module-versions": {
                "Gtk": "4.0",
                "Gdk": "4.0",
            },
        },
    }

a = Analysis(
    ["main.py"],
    pathex=["."],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig=hooksconfig,
    runtime_hooks=runtime_hooks,
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="evelina",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    icon=icon,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="evelina",
)
