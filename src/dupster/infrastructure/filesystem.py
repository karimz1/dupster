import os
import shutil
import subprocess
import sys
from collections.abc import Iterator
from datetime import datetime

from dupster.domain.models import FileEntry

ZIP_EXT = ".zip"


def iter_entries(root: str, follow_symlinks: bool = False) -> Iterator[FileEntry]:
    """Walk `root` yielding FileEntry.

    Uses os.scandir so that size, device, inode and mtime all come from the one
    stat the directory read already performs. The previous os.walk plus
    os.path.isfile approach paid a second stat syscall for every file.
    """
    stack = [root]
    seen_dirs = set()
    while stack:
        current = stack.pop()
        try:
            with os.scandir(current) as it:
                for entry in it:
                    try:
                        if entry.is_dir(follow_symlinks=follow_symlinks):
                            # Guard against symlink loops when following is on.
                            if follow_symlinks:
                                key = os.path.realpath(entry.path)
                                if key in seen_dirs:
                                    continue
                                seen_dirs.add(key)
                            stack.append(entry.path)
                            continue
                        if not entry.is_file(follow_symlinks=follow_symlinks):
                            continue
                        st = entry.stat(follow_symlinks=follow_symlinks)
                    except OSError:
                        continue
                    yield FileEntry(
                        path=entry.path,
                        size=st.st_size,
                        dev=st.st_dev,
                        ino=st.st_ino,
                        mtime_ns=getattr(st, "st_mtime_ns", 0),
                        nlink=getattr(st, "st_nlink", 1),
                        is_zip=entry.name.lower().endswith(ZIP_EXT),
                    )
        except OSError:
            continue


def scan_entries(root: str, follow_symlinks: bool = False) -> list[FileEntry]:
    return list(iter_entries(root, follow_symlinks=follow_symlinks))


def list_files(root: str) -> list[str]:
    return [e.path for e in iter_entries(root)]


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


def _launch_detached(command: list[str]) -> bool:
    try:
        kwargs = {
            "stdin": subprocess.DEVNULL,
            "stdout": subprocess.DEVNULL,
            "stderr": subprocess.DEVNULL,
        }
        if os.name == "posix":
            kwargs["start_new_session"] = True
        subprocess.Popen(command, **kwargs)
        return True
    except Exception:
        return False


def open_file(path: str) -> bool:
    if sys.platform.startswith("darwin"):
        return _launch_detached(["open", path])
    if os.name == "nt":
        try:
            os.startfile(path)  # type: ignore[attr-defined]
            return True
        except Exception:
            return False
    if os.name == "posix":
        opener = shutil.which("xdg-open")
        if not opener:
            return False
        return _launch_detached([opener, path])
    return False
