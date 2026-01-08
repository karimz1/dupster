import os
import subprocess
import sys
from datetime import datetime


def list_files(root: str) -> list[str]:
    items: list[str] = []
    for r, _, files in os.walk(root):
        for name in files:
            p = os.path.join(r, name)
            if os.path.isfile(p):
                items.append(p)
    return items


def get_size(path: str) -> int:
    try:
        return os.path.getsize(path)
    except Exception:
        return 0


def get_mtime_str(path: str) -> str:
    try:
        ts = os.path.getmtime(path)
        return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")
    except Exception:
        return "—"


def open_file(path: str) -> None:
    try:
        if sys.platform.startswith("darwin"):
            subprocess.call(["open", path])
        elif os.name == "nt":
            os.startfile(path)  # type: ignore[attr-defined]
        elif os.name == "posix":
            subprocess.call(["xdg-open", path])
    except Exception:
        pass
