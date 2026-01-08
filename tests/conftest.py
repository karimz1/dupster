import zipfile
from pathlib import Path

import pytest

from dupster.infrastructure.hashing import compute_file_hash


@pytest.fixture()
def dupe_dataset(tmp_path: Path):
    root = tmp_path
    content_a = b"A" * 1024
    content_b = b"B" * 2048
    (root / "one").mkdir(parents=True, exist_ok=True)
    (root / "two").mkdir(parents=True, exist_ok=True)
    (root / "three").mkdir(parents=True, exist_ok=True)
    (root / "unique").mkdir(parents=True, exist_ok=True)
    (root / "same-name-1").mkdir(parents=True, exist_ok=True)
    (root / "same-name-2").mkdir(parents=True, exist_ok=True)
    (root / "zip").mkdir(parents=True, exist_ok=True)

    a1 = root / "one" / "a1.bin"
    a1.write_bytes(content_a)
    a2 = root / "two" / "a2.bin"
    a2.write_bytes(content_a)
    b1 = root / "three" / "b1.bin"
    b1.write_bytes(content_b)
    b2 = root / "three" / "b2.bin"
    b2.write_bytes(content_b)
    (root / "unique" / "u.bin").write_bytes(b"U" * 512)
    (root / "same-name-1" / "x.txt").write_bytes(b"C" * 512)
    (root / "same-name-2" / "x.txt").write_bytes(b"D" * 512)

    z = root / "zip" / "singlefile.zip"
    with zipfile.ZipFile(z, "w", compression=zipfile.ZIP_STORED) as zipf:
        zipf.writestr("inside.txt", content_a)

    hash_a = compute_file_hash(str(a1))
    hash_b = compute_file_hash(str(b1))

    expected = {
        hash_a: {str(a1), str(a2), str(z)},
        hash_b: {str(b1), str(b2)},
    }

    return {
        "root": str(root),
        "hash_a": hash_a,
        "hash_b": hash_b,
        "expected": expected,
    }
