import subprocess
import sys

from dupster.infrastructure import filesystem
from dupster.infrastructure.filesystem import get_mtime_str, get_size, list_files, open_file


def test_list_files_excludes_dirs_and_is_recursive(tmp_path):
    (tmp_path / "a").mkdir()
    (tmp_path / "a" / "f1.txt").write_text("x")
    (tmp_path / "b" / "c").mkdir(parents=True)
    (tmp_path / "b" / "c" / "f2.txt").write_text("y")
    files = set(list_files(str(tmp_path)))
    assert str(tmp_path / "a" / "f1.txt") in files
    assert str(tmp_path / "b" / "c" / "f2.txt") in files
    assert str(tmp_path / "a") not in files


def test_get_size_and_mtime_str_resilience(tmp_path):
    p = tmp_path / "f.txt"
    p.write_text("hello")
    assert get_size(str(p)) == 5
    missing = tmp_path / "missing.txt"
    assert get_size(str(missing)) == 0
    ts = get_mtime_str(str(p))
    assert isinstance(ts, str) and len(ts) >= 10
    assert get_mtime_str(str(missing)) == "—"


def test_open_file_launches_detached_on_macos(monkeypatch, tmp_path):
    path = tmp_path / "duplicate.txt"
    calls = []

    def popen(command, **kwargs):
        calls.append((command, kwargs))
        return object()

    monkeypatch.setattr(sys, "platform", "darwin")
    monkeypatch.setattr(filesystem.subprocess, "Popen", popen)

    assert open_file(str(path))
    assert calls == [
        (
            ["open", str(path)],
            {
                "stdin": subprocess.DEVNULL,
                "stdout": subprocess.DEVNULL,
                "stderr": subprocess.DEVNULL,
                "start_new_session": True,
            },
        )
    ]


def test_open_file_reports_launch_failure(monkeypatch, tmp_path):
    path = tmp_path / "duplicate.txt"

    def popen(command, **kwargs):
        raise OSError("opener failed")

    monkeypatch.setattr(sys, "platform", "darwin")
    monkeypatch.setattr(filesystem.subprocess, "Popen", popen)

    assert not open_file(str(path))
