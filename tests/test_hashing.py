import io
import os
import zipfile
from dupster.infrastructure.hashing import compute_file_hash, compute_zip_content_hash


def test_file_and_zip_content_hash_match(tmp_path):
    p1 = tmp_path / "a.txt"
    p1.write_bytes(b"hello world" * 1000)
    zpath = tmp_path / "a.zip"
    with zipfile.ZipFile(zpath, "w", compression=zipfile.ZIP_STORED) as z:
        z.writestr("folder/file.txt", p1.read_bytes())

    f_hash = compute_file_hash(str(p1))
    z_hash = compute_zip_content_hash(str(zpath))

    assert isinstance(f_hash, str)
    assert isinstance(z_hash, str)
    assert f_hash == z_hash

