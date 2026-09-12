"""OS-path safety guards.

Files that live inside system-owned directories must *never* be treated as
duplicates, even if byte-identical copies exist elsewhere.  Offering to delete
them would:

  - risk breaking the operating system or installed applications,
  - bypass the OS package-manager / SIP lifecycle that owns those files,
  - in the best case confuse the user who never expected system paths here.

``is_os_protected`` is the single gate.  Call it once per candidate path in
the scanner pipeline and drop the entry when it returns ``True``.
"""

import os
import sys

# ---------------------------------------------------------------------------
# Per-platform prefix tables
# ---------------------------------------------------------------------------

# macOS — System Integrity Protection (SIP) protects most of these at the
# kernel level, but we guard them at the application level too so that a
# scan run as root or in a container is still safe.
#
# macOS symlinks /etc -> /private/etc, /var -> /private/var, /tmp ->
# /private/tmp.  We check *both* the canonical real path prefix and the
# logical symlink form so the guard fires regardless of how the path was
# obtained.
_MACOS_PROTECTED: tuple[str, ...] = (
    "/System/",
    "/usr/",
    "/bin/",
    "/sbin/",
    # /private/* is the real location of the /etc, /var and /tmp symlinks.
    # We protect only the genuinely system-owned subtrees, NOT /private/var/folders
    # which is where macOS places per-user temporary directories (and pytest tmp_path).
    "/private/etc/",
    "/private/var/db/",
    "/private/var/root/",
    "/private/var/run/",
    "/private/var/spool/",
    "/private/var/vm/",
    "/private/var/protected_data/",
    # Logical aliases for the above (via OS symlinks).
    "/etc/",
    "/var/",
    # Apple-managed library trees.
    "/Library/Apple/",
    "/Library/Extensions/",
    "/Library/Frameworks/",
    # Developer tools shipped by Apple (Xcode.app etc.) live here.
    "/Applications/Xcode.app/",
    "/Applications/Xcode-beta.app/",
)

# Linux — includes distro-agnostic FHS roots, snap, and the pseudo-filesystems
# that should never be touched.
_LINUX_PROTECTED: tuple[str, ...] = (
    "/usr/",
    "/bin/",
    "/sbin/",
    "/lib/",
    "/lib32/",
    "/lib64/",
    "/libx32/",
    "/etc/",
    "/boot/",
    "/sys/",
    "/proc/",
    "/dev/",
    "/run/",
    "/snap/",
    "/nix/",       # NixOS / nix store
    "/opt/homebrew/",  # Homebrew on Apple Silicon (used on Linux too sometimes)
)

# Windows — normalised to lower-case for case-insensitive comparison.
# We only protect Microsoft/Windows-owned directories, not all of Program
# Files, because third-party apps installed there should remain scannable.
_WINDOWS_PROTECTED_LOWER: tuple[str, ...] = (
    "\\windows\\",
    "\\program files\\microsoft ",       # Microsoft apps under Program Files
    "\\program files (x86)\\microsoft ",  # 32-bit Microsoft apps
    "\\programdata\\microsoft\\",
    "\\system volume information\\",
    "\\recovery\\",
    "\\$recycle.bin\\",
    "\\$winre_backup_partition.marker",
)


def is_os_protected(path: str) -> bool:
    """Return ``True`` if *path* is inside a known OS or system directory.

    The check is intentionally conservative: only well-known, clearly
    system-owned prefix trees are listed.  User home directories and
    application data folders are never blocked.

    Examples
    --------
    >>> is_os_protected("/System/Library/CoreServices/Finder.app")
    True          # macOS system tree — always protected
    >>> is_os_protected("/usr/bin/python3")
    True          # Unix system binaries — protected on macOS and Linux
    >>> is_os_protected("/Users/alice/Documents/report.pdf")
    False         # user data — never protected
    """
    if sys.platform == "darwin":
        return _is_macos_protected(path)
    if os.name == "nt":
        return _is_windows_protected(path)
    # Generic POSIX / Linux.
    return _is_linux_protected(path)


# ---------------------------------------------------------------------------
# Platform helpers (kept private so callers only use ``is_os_protected``)
# ---------------------------------------------------------------------------


def _is_macos_protected(path: str) -> bool:
    return any(path.startswith(prefix) for prefix in _MACOS_PROTECTED)


def _is_linux_protected(path: str) -> bool:
    return any(path.startswith(prefix) for prefix in _LINUX_PROTECTED)


def _is_windows_protected(path: str) -> bool:
    # Normalise: lower-case and forward slashes -> backslashes.
    normalised = path.lower().replace("/", "\\")
    # Ensure we always have a trailing separator so a bare drive root like
    # "c:\windows" still matches "\\windows\\" as a substring.
    if not normalised.endswith("\\"):
        normalised += "\\"
    return any(pat in normalised for pat in _WINDOWS_PROTECTED_LOWER)
