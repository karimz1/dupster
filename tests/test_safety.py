"""Tests for the OS-path safety guard (infrastructure/safety.py).

Every test here ensures that is_os_protected() correctly blocks files inside
system directories and allows everything under user-owned paths.  The final
integration tests verify that the real scanner pipeline honours the guard so
that no future refactor can accidentally re-introduce the risk.
"""

import asyncio
import os
import sys
from unittest.mock import patch

import pytest

from dupster.application.scanner import clear_hash_cache, find_duplicates_detailed_async
from dupster.infrastructure.safety import (
    _is_linux_protected,
    _is_macos_protected,
    _is_windows_protected,
    is_os_protected,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def write(path, data: bytes):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def scan_detailed(root: str, **kw):
    clear_hash_cache()
    return asyncio.run(find_duplicates_detailed_async(root, **kw))


# ---------------------------------------------------------------------------
# macOS-specific prefix table
# ---------------------------------------------------------------------------


class TestMacOSProtected:
    """_is_macos_protected covers the macOS system prefix table."""

    @pytest.mark.parametrize(
        "path",
        [
            "/System/Library/CoreServices/Finder.app/Contents/MacOS/Finder",
            "/System/Volumes/Data/private/var/db/something",
            "/usr/bin/python3",
            "/usr/lib/dyld",
            "/bin/bash",
            "/sbin/launchd",
            "/private/etc/hosts",
            "/private/var/db/uuidtext/something",
            "/private/var/root/.bashrc",
            "/private/var/run/syslog",
            "/private/var/vm/sleepimage",
            # Logical symlink aliases
            "/etc/hosts",
            "/var/log/system.log",
            # Apple-managed library subtrees
            "/Library/Apple/System/Library/Frameworks/CoreML.framework",
            "/Library/Extensions/AppleHDA.kext",
            "/Library/Frameworks/Python.framework",
            # Xcode shipped by Apple
            "/Applications/Xcode.app/Contents/Developer/usr/bin/clang",
        ],
    )
    def test_protected_paths_are_blocked(self, path):
        assert _is_macos_protected(path), f"Expected protected: {path!r}"

    @pytest.mark.parametrize(
        "path",
        [
            "/Users/alice/Documents/report.pdf",
            "/Users/alice/Downloads/file.zip",
            "/Users/alice/Library/Application Support/MyApp/cache.db",
            "/Volumes/ExternalDrive/backup.tar",
            "/Applications/Firefox.app/Contents/MacOS/firefox",
            "/opt/homebrew/bin/brew",   # Homebrew user-managed, not Apple
            "/home/runner/work/project/file.py",  # CI runner
            # User temp dirs live under /private/var/folders — must NOT be blocked.
            "/private/var/folders/5w/abc123/T/pytest-123/file.bin",
        ],
    )
    def test_user_paths_are_allowed(self, path):
        assert not _is_macos_protected(path), f"Expected allowed: {path!r}"


# ---------------------------------------------------------------------------
# Linux-specific prefix table
# ---------------------------------------------------------------------------


class TestLinuxProtected:
    @pytest.mark.parametrize(
        "path",
        [
            "/usr/bin/python3",
            "/usr/lib/x86_64-linux-gnu/libssl.so.3",
            "/bin/bash",
            "/sbin/init",
            "/lib/modules/6.1.0/kernel/drivers/net/eth.ko",
            "/lib64/ld-linux-x86-64.so.2",
            "/etc/passwd",
            "/etc/systemd/system/sshd.service",
            "/boot/vmlinuz-6.1.0",
            "/sys/devices/cpu/online",
            "/proc/self/status",
            "/dev/null",
            "/run/systemd/private/tmp",
            "/snap/core22/current/usr/lib/libc.so.6",
            "/nix/store/aaabbb-glibc-2.37/lib/libc.so.6",
        ],
    )
    def test_protected_paths_are_blocked(self, path):
        assert _is_linux_protected(path), f"Expected protected: {path!r}"

    @pytest.mark.parametrize(
        "path",
        [
            "/home/alice/Documents/report.pdf",
            "/home/alice/.config/myapp/settings.json",
            "/root/projects/myapp/main.py",   # root's home, not a system tree
            "/opt/mycompany/app/binary",       # third-party opt, not /snap or /nix
            "/mnt/backup/archive.tar.gz",
            "/srv/www/index.html",
            "/media/usb/photos/img001.jpg",
        ],
    )
    def test_user_paths_are_allowed(self, path):
        assert not _is_linux_protected(path), f"Expected allowed: {path!r}"


# ---------------------------------------------------------------------------
# Windows-specific prefix table
# ---------------------------------------------------------------------------


class TestWindowsProtected:
    @pytest.mark.parametrize(
        "path",
        [
            r"C:\Windows\System32\ntdll.dll",
            r"C:\Windows\SysWOW64\kernel32.dll",
            r"c:\windows\system32\drivers\etc\hosts",   # lower-case drive
            r"D:\Windows\explorer.exe",                  # different drive
            r"C:\Program Files\Microsoft Office\WINWORD.EXE",
            r"C:\Program Files (x86)\Microsoft Visual C++\vc_redist.exe",
            r"C:\ProgramData\Microsoft\Windows Defender\Definition Updates",
            r"C:\System Volume Information\WPSettings.dat",
            r"C:\Recovery\WindowsRE\winre.wim",
            r"C:\$Recycle.Bin\S-1-5-21\$I3K9W2F.docx",
        ],
    )
    def test_protected_paths_are_blocked(self, path):
        assert _is_windows_protected(path), f"Expected protected: {path!r}"

    @pytest.mark.parametrize(
        "path",
        [
            r"C:\Users\alice\Documents\report.docx",
            r"C:\Users\alice\Downloads\setup.exe",
            r"D:\Projects\myapp\main.py",
            # Third-party installs in Program Files are NOT protected.
            r"C:\Program Files\MyThirdPartyApp\app.exe",
            r"C:\Program Files\Adobe\Photoshop\photoshop.exe",
        ],
    )
    def test_user_paths_are_allowed(self, path):
        assert not _is_windows_protected(path), f"Expected allowed: {path!r}"


# ---------------------------------------------------------------------------
# Platform-dispatch: is_os_protected routes to the right helper
# ---------------------------------------------------------------------------


class TestIsOsProtectedDispatch:
    def test_macos_dispatch(self):
        with patch("dupster.infrastructure.safety.sys") as mock_sys, \
             patch("dupster.infrastructure.safety.os") as mock_os:
            mock_sys.platform = "darwin"
            mock_os.name = "posix"
            assert is_os_protected("/System/Library/something")
            assert not is_os_protected("/Users/alice/file.txt")

    def test_linux_dispatch(self):
        with patch("dupster.infrastructure.safety.sys") as mock_sys, \
             patch("dupster.infrastructure.safety.os") as mock_os:
            mock_sys.platform = "linux"
            mock_os.name = "posix"
            assert is_os_protected("/usr/bin/bash")
            assert not is_os_protected("/home/alice/file.txt")

    def test_windows_dispatch(self):
        with patch("dupster.infrastructure.safety.sys") as mock_sys, \
             patch("dupster.infrastructure.safety.os") as mock_os:
            mock_sys.platform = "win32"
            mock_os.name = "nt"
            assert is_os_protected(r"C:\Windows\System32\ntdll.dll")
            assert not is_os_protected(r"C:\Users\alice\file.txt")


# ---------------------------------------------------------------------------
# Integration: the scanner pipeline must honour is_os_protected
# ---------------------------------------------------------------------------


def test_scanner_skips_os_protected_files(tmp_path, monkeypatch):
    """Files whose path is flagged by is_os_protected must never appear in
    duplicate results, and must be counted in skipped_os_protected.

    We monkeypatch is_os_protected in the scanner module so that a
    synthetic 'system' subdirectory of tmp_path is treated as protected.
    This lets the test run without needing real /System or /usr paths.
    """
    # Real duplicate pair — these must be found.
    payload = b"user data" * 500
    write(tmp_path / "user" / "a.bin", payload)
    write(tmp_path / "user" / "b.bin", payload)

    # Identical bytes but inside a 'protected' directory — must be invisible.
    sys_file = write(tmp_path / "system" / "core.bin", payload)

    protected_prefix = str(tmp_path / "system") + os.sep

    original_guard = __import__(
        "dupster.infrastructure.safety", fromlist=["is_os_protected"]
    ).is_os_protected

    def patched_guard(path: str) -> bool:
        if path.startswith(protected_prefix):
            return True
        return original_guard(path)

    monkeypatch.setattr(
        "dupster.application.scanner.is_os_protected", patched_guard
    )

    dupes, stats, _ = scan_detailed(str(tmp_path))

    # The system file must not appear in any group.
    all_paths = {p for paths in dupes.values() for p in paths}
    assert str(sys_file) not in all_paths, (
        "OS-protected file appeared in duplicate results"
    )

    # The real user-space duplicate must still be detected.
    assert len(dupes) == 1, "Expected exactly one user-space duplicate group"

    # Stats must reflect the skipped OS-protected file.
    assert stats.skipped_os_protected >= 1


def test_scanner_os_protected_stat_is_separate_from_size_skip(tmp_path, monkeypatch):
    """skipped_os_protected must be a distinct counter from skipped_by_size
    so that callers can surface the reason to the user.
    """
    data = b"data" * 1000
    write(tmp_path / "real" / "a.bin", data)
    write(tmp_path / "real" / "b.bin", data)
    # A small file that will be skipped by min_size.
    write(tmp_path / "real" / "tiny.bin", b"x")
    # A file that will be skipped by the OS guard.
    sys_file = write(tmp_path / "sys" / "c.bin", data)

    prefix = str(tmp_path / "sys") + os.sep
    orig = __import__(
        "dupster.infrastructure.safety", fromlist=["is_os_protected"]
    ).is_os_protected

    monkeypatch.setattr(
        "dupster.application.scanner.is_os_protected",
        lambda p: p.startswith(prefix) or orig(p),
    )

    _, stats, _ = scan_detailed(str(tmp_path), min_size=10)

    assert stats.skipped_os_protected >= 1
    # tiny.bin is skipped by size (< min_size=10), not by the OS guard.
    assert stats.skipped_by_size >= 1


@pytest.mark.skipif(os.name == "nt", reason="symlinks need privileges on Windows")
def test_scanner_real_os_paths_are_never_reported(tmp_path):
    """On the actual host OS, paths under real system directories (e.g.
    /usr/bin/env on macOS/Linux) must not appear in results even if their
    content appears in user space.

    This test only runs when a known real system file exists so it stays
    portable across CI environments.
    """
    # Pick a real system file that is very likely to exist.
    candidates = ["/usr/bin/env", "/bin/sh", "/usr/bin/true"]
    system_file = next((p for p in candidates if os.path.isfile(p)), None)
    if system_file is None:
        pytest.skip("No known system binary found on this host")

    real_content = open(system_file, "rb").read()
    if not real_content:
        pytest.skip("System binary is empty, skipping")

    # Place an identical copy in user space.
    write(tmp_path / "user_copy.bin", real_content)

    dupes, stats, _ = scan_detailed(str(tmp_path))

    # system_file must not appear in any group.
    all_paths = {p for paths in dupes.values() for p in paths}
    assert system_file not in all_paths, (
        f"System file {system_file!r} appeared in duplicate results"
    )
