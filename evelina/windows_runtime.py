"""Пути GTK для собранной Windows-программы."""

import os
import sys


def configure():
    if not (getattr(sys, "frozen", False) and sys.platform == "win32"):
        return
    base = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    os.environ["PATH"] = base + os.pathsep + os.environ.get("PATH", "")
    typelibs = []
    for path in (
        os.path.join(base, "lib", "girepository-1.0"),
        os.environ.get("GI_TYPELIB_PATH", ""),
        os.path.join(base, "gi_typelibs"),
    ):
        for item in path.split(os.pathsep):
            if item and item not in typelibs and os.path.isdir(item):
                typelibs.append(item)
    if typelibs:
        os.environ["GI_TYPELIB_PATH"] = os.pathsep.join(typelibs)
    share = os.path.join(base, "share")
    xdg = [item for item in os.environ.get("XDG_DATA_DIRS", "").split(os.pathsep) if item]
    if share not in xdg:
        xdg.insert(0, share)
    os.environ["XDG_DATA_DIRS"] = os.pathsep.join(xdg)
    os.environ["GTK_EXE_PREFIX"] = base
    os.environ["GTK_DATA_PREFIX"] = base
    os.environ["GTK_PATH"] = base
    for loaders in (
        os.path.join(base, "lib", "gdk-pixbuf", "loaders.cache"),
        os.path.join(base, "lib", "gdk-pixbuf-2.0", "2.10.0", "loaders.cache"),
    ):
        if os.path.exists(loaders):
            os.environ["GDK_PIXBUF_MODULE_FILE"] = loaders
            os.environ["GDK_PIXBUF_MODULEDIR"] = os.path.dirname(loaders)
            break


configure()
