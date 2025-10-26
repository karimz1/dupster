from pathlib import Path
from dupster.infrastructure.filesystem import list_files, get_size, get_mtime_str


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

