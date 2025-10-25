from dupster.infrastructure.hashing import compute_file_hash, compute_zip_content_hash


def test_file_hash_missing_returns_none(tmp_path):
    missing = tmp_path / "nope.bin"
    assert compute_file_hash(str(missing)) is None


def test_zip_hash_invalid_returns_none(tmp_path):
    not_zip = tmp_path / "data.txt"
    not_zip.write_text("not a zip")
    assert compute_zip_content_hash(str(not_zip)) is None

