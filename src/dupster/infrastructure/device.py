"""Storage device detection and per-device I/O tuning.

The optimal read strategy depends entirely on the underlying hardware:

* NVMe/SSD have no seek penalty and need a deep request queue to reach full
  throughput, so we issue many concurrent reads.
* Spinning disks are destroyed by concurrent reads (the head thrashes between
  cylinders). They want a single reader walking the disk in one direction,
  which is the classic elevator/SCAN disk-scheduling algorithm.

Detection is best effort and cached. It can always be overridden.
"""

import os
import subprocess
import sys
from typing import Optional

SSD = "ssd"
HDD = "hdd"

_ENV_OVERRIDE = "DUPSTER_DEVICE_TYPE"

# Cache per st_dev, detection can involve sysfs reads or a subprocess.
_cache: dict = {}


def _linux_rotational(dev: int) -> Optional[str]:
    major, minor = os.major(dev), os.minor(dev)
    sysfs = f"/sys/dev/block/{major}:{minor}"
    try:
        real = os.path.realpath(sysfs)
    except OSError:
        return None
    # A partition (sda1) has no queue/ of its own, walk up to the parent disk.
    for candidate in (real, os.path.dirname(real)):
        rot_path = os.path.join(candidate, "queue", "rotational")
        try:
            with open(rot_path) as fh:
                return HDD if fh.read().strip() == "1" else SSD
        except OSError:
            continue
    return None


def _darwin_solid_state(path: str) -> Optional[str]:
    try:
        out = subprocess.run(
            ["diskutil", "info", "-plist", path],
            capture_output=True,
            timeout=5,
            check=False,
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    if not out:
        return None
    try:
        import plistlib

        info = plistlib.loads(out)
    except Exception:
        return None
    solid = info.get("SolidState")
    if solid is None:
        return None
    return SSD if solid else HDD


def detect_device_type(path: str, dev: Optional[int] = None) -> str:
    """Return SSD or HDD for the device backing `path`. Falls back to SSD."""
    override = os.environ.get(_ENV_OVERRIDE, "").strip().lower()
    if override in (SSD, HDD):
        return override

    if dev is None:
        try:
            dev = os.stat(path).st_dev
        except OSError:
            return SSD
    if dev in _cache:
        return _cache[dev]

    result = None
    if sys.platform.startswith("linux"):
        result = _linux_rotational(dev)
    elif sys.platform == "darwin":
        result = _darwin_solid_state(path)

    # Unknown hardware is assumed solid state. Almost every machine running this
    # in 2026 is, and over-parallelising an SSD costs far less than
    # under-parallelising one.
    result = result or SSD
    _cache[dev] = result
    return result


def default_workers(device_type: str) -> int:
    """Concurrent readers for one physical device."""
    if device_type == HDD:
        # One reader. Combined with inode-ordered reads this turns a random
        # seek storm into a single sweep across the platter.
        return 1
    cpu = os.cpu_count() or 4
    return min(32, cpu * 4)


def clear_cache() -> None:
    _cache.clear()
