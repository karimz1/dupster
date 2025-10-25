import asyncio
from pathlib import Path
from dupster.application.scanner import find_duplicates_by_hash_async


def write(p: Path, data: bytes) -> Path:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(data)
    return p


def test_scanner_finds_duplicates(tmp_path):
    data1 = b"alpha" * 1024
    data2 = b"beta" * 2048

    write(tmp_path / "dir1" / "a.bin", data1)
    write(tmp_path / "dir1" / "b.bin", data2)
    write(tmp_path / "dir2" / "c.bin", data1)
    write(tmp_path / "dir3" / "d.bin", data2)
    write(tmp_path / "dir3" / "unique.bin", b"unique")

    hm = asyncio.run(find_duplicates_by_hash_async(str(tmp_path)))

    dup_counts = sorted(len(v) for v in hm.values())
    assert dup_counts == [2, 2]

