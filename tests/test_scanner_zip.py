import asyncio
import zipfile
from pathlib import Path
from dupster.application.scanner import find_duplicates_by_hash_async


def test_scanner_detects_duplicates_across_zip_and_files(tmp_path):
    data = b"same-content" * 100
    p1 = tmp_path / "dir1" / "a.txt"; p1.parent.mkdir(parents=True, exist_ok=True); p1.write_bytes(data)
    p2 = tmp_path / "dir2" / "b.txt"; p2.parent.mkdir(parents=True, exist_ok=True); p2.write_bytes(data)
    z = tmp_path / "pack.zip"
    with zipfile.ZipFile(z, "w", compression=zipfile.ZIP_STORED) as zipf:
        zipf.writestr("inner/file.txt", data)

    hm = asyncio.run(find_duplicates_by_hash_async(str(tmp_path)))
    assert any(len(files) == 3 for files in hm.values())

