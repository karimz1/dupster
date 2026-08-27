import os

from dupster.infrastructure.hashing import (
    PROBE_SIZE,
    bytewise_split,
    compute_edge_hash,
    compute_head_hash,
    zip_content_size,
)


def w(tmp_path, name, data):
    p = tmp_path / name
    p.write_bytes(data)
    return str(p)


def test_head_hash_ignores_bytes_past_the_probe(tmp_path):
    head = b"H" * PROBE_SIZE
    a = w(tmp_path, "a", head + b"AAAA")
    b = w(tmp_path, "b", head + b"BBBB")
    assert compute_head_hash(a) == compute_head_hash(b)


def test_head_hash_detects_early_difference(tmp_path):
    a = w(tmp_path, "a", b"A" + b"x" * 10000)
    b = w(tmp_path, "b", b"B" + b"x" * 10000)
    assert compute_head_hash(a) != compute_head_hash(b)


def test_edge_hash_detects_tail_difference(tmp_path):
    body = b"z" * 100000
    a = w(tmp_path, "a", body + b"A")
    b = w(tmp_path, "b", body + b"B")
    assert compute_edge_hash(a, os.path.getsize(a)) != compute_edge_hash(b, os.path.getsize(b))


def test_edge_hash_detects_middle_difference(tmp_path):
    size = 100000
    a_data = bytearray(b"z" * size)
    b_data = bytearray(b"z" * size)
    a_data[size // 2] = ord("A")
    b_data[size // 2] = ord("B")
    a = w(tmp_path, "a", bytes(a_data))
    b = w(tmp_path, "b", bytes(b_data))
    assert compute_edge_hash(a, size) != compute_edge_hash(b, size)


def test_probe_hashes_return_none_for_missing_file(tmp_path):
    missing = str(tmp_path / "nope")
    assert compute_head_hash(missing) is None
    assert compute_edge_hash(missing, 100) is None


def test_zip_content_size_ignores_compression(tmp_path):
    import zipfile

    data = b"compressible " * 4000
    z = tmp_path / "p.zip"
    with zipfile.ZipFile(z, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("a.txt", data)
    assert zip_content_size(str(z)) == len(data)
    assert z.stat().st_size < len(data)


def test_zip_content_size_invalid_returns_none(tmp_path):
    p = w(tmp_path, "not.zip", b"definitely not a zip")
    assert zip_content_size(p) is None


def test_bytewise_split_groups_identical_files(tmp_path):
    data = os.urandom(500000)
    a = w(tmp_path, "a", data)
    b = w(tmp_path, "b", data)
    assert bytewise_split([a, b]) == [[a, b]] or bytewise_split([a, b]) == [[b, a]]


def test_bytewise_split_separates_near_identical_files(tmp_path):
    data = b"q" * 500000
    a = w(tmp_path, "a", data)
    b = w(tmp_path, "b", data)
    c = w(tmp_path, "c", data[:-1] + b"Z")
    groups = bytewise_split([a, b, c])
    assert len(groups) == 1
    assert sorted(groups[0]) == sorted([a, b])


def test_bytewise_split_handles_prefix_relationship(tmp_path):
    a = w(tmp_path, "a", b"x" * 100000)
    b = w(tmp_path, "b", b"x" * 50000)
    assert bytewise_split([a, b]) == []


def test_bytewise_split_handles_empty_and_single(tmp_path):
    a = w(tmp_path, "a", b"")
    b = w(tmp_path, "b", b"")
    assert sorted(bytewise_split([a, b])[0]) == sorted([a, b])
    assert bytewise_split([a]) == []
    assert bytewise_split([]) == []
