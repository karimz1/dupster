"""Correctness of the staged pipeline.

The staged scanner must return exactly what an exhaustive "hash every file"
scan returns. Every test here either pins an adversarial shape that a cheap
filter could plausibly get wrong, or compares the whole pipeline against a
brute force reference.
"""

import asyncio
import os
import random
import zipfile

import pytest

from dupster.application.scanner import (
    clear_hash_cache,
    find_duplicates_by_hash_async,
    find_duplicates_detailed_async,
)
from dupster.infrastructure.filesystem import iter_entries
from dupster.infrastructure.hashing import compute_file_hash, compute_zip_content_hash
from dupster.infrastructure.safety import is_os_protected


@pytest.fixture(autouse=True)
def _clean_cache():
    clear_hash_cache()
    yield
    clear_hash_cache()


def brute_force(root: str) -> dict:
    """The exhaustive reference: full hash of every file, no filtering.

    Mirrors the same safety exclusions as the real scanner so that the
    differential test stays valid even when the random tree contains
    zero-byte files or files inside OS-protected paths.
    """
    by_hash: dict = {}
    for entry in iter_entries(root):
        # Skip zero-byte files — same rule as the real scanner.
        if entry.size == 0:
            continue
        # Skip OS-protected paths — same rule as the real scanner.
        if is_os_protected(entry.path):
            continue
        if entry.path.lower().endswith(".zip"):
            digest = compute_zip_content_hash(entry.path)
        else:
            digest = compute_file_hash(entry.path)
        if digest:
            by_hash.setdefault(digest, []).append(entry.path)
    return {h: sorted(p) for h, p in by_hash.items() if len(p) > 1}


def normalise(hm: dict) -> set:
    """Compare as a set of path groups, independent of digest values."""
    return {tuple(sorted(paths)) for paths in hm.values()}


def scan(root: str, **kw) -> dict:
    return asyncio.run(find_duplicates_by_hash_async(root, **kw))


def write(path, data: bytes):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


# --------------------------------------------------------------------------
# Adversarial shapes: each targets one stage of the pipeline
# --------------------------------------------------------------------------


def test_same_size_different_head_is_not_duplicate(tmp_path):
    """Stage 3 must split these, and must not report them."""
    write(tmp_path / "a.bin", b"A" + b"x" * 100000)
    write(tmp_path / "b.bin", b"B" + b"x" * 100000)
    assert scan(str(tmp_path)) == {}


def test_same_head_different_tail_is_not_duplicate(tmp_path):
    """Identical 64 KiB header, differing final byte. Stage 4 exists for this."""
    head = b"H" * 65536
    write(tmp_path / "a.bin", head + b"x" * 50000 + b"A")
    write(tmp_path / "b.bin", head + b"x" * 50000 + b"B")
    assert scan(str(tmp_path)) == {}


def test_same_head_and_edges_different_middle_is_not_duplicate(tmp_path):
    """The nastiest case: every probed region matches, only unprobed bytes differ.

    Sampling can never rule this out, so it proves the full hash really runs
    and that the probes are used purely as a filter.
    """
    size = 400000
    base = bytearray(b"z" * size)
    a = bytearray(base)
    b = bytearray(base)
    # Change a byte at 1/4 through, which no probe reads.
    a[size // 4] = ord("A")
    b[size // 4] = ord("B")
    write(tmp_path / "a.bin", bytes(a))
    write(tmp_path / "b.bin", bytes(b))
    assert scan(str(tmp_path)) == {}


def test_identical_large_files_are_found(tmp_path):
    data = os.urandom(300000)
    write(tmp_path / "one" / "a.bin", data)
    write(tmp_path / "two" / "b.bin", data)
    assert normalise(scan(str(tmp_path))) == {
        (str(tmp_path / "one" / "a.bin"), str(tmp_path / "two" / "b.bin"))
    }


def test_zero_byte_files_are_never_reported_as_duplicates(tmp_path):
    """Zero-byte files must be unconditionally excluded from results.

    All empty files share the same SHA-256, but reporting them as duplicates is
    dangerous: deleting any of them reclaims exactly 0 bytes and may silently
    break OS or application behaviour.  macOS, for instance, drops zero-byte
    placeholder files (e.g. ~/Downloads/.localized, ~/Downloads/sessions) that
    apps and Finder depend on.  Deleting a placeholder is indistinguishable from
    deleting one of several real empty files, so the safe choice is to never
    surface them at all.
    """
    write(tmp_path / "a.bin", b"")
    write(tmp_path / "b.bin", b"")
    write(tmp_path / "c.bin", b"x")  # non-empty, must not appear either
    assert scan(str(tmp_path)) == {}


def test_files_below_probe_threshold_still_compared(tmp_path):
    """Tiny files skip probing and go straight to the full hash."""
    write(tmp_path / "a.txt", b"hello")
    write(tmp_path / "b.txt", b"hello")
    write(tmp_path / "c.txt", b"world")
    assert normalise(scan(str(tmp_path))) == {(str(tmp_path / "a.txt"), str(tmp_path / "b.txt"))}


@pytest.mark.skipif(os.name == "nt", reason="symlinks need privileges on Windows")
def test_macos_downloads_placeholder_pattern(tmp_path):
    """Model the exact scenario from the bug report.

    ~/Downloads commonly contains zero-byte placeholder files created by macOS
    and web-browser sessions (.localized, account, data, sessions, sign-in, l).
    They all share the same SHA-256 because they are all empty.  Dupster must
    not report any of them as duplicates, and must not report a mix of empty
    and non-empty files as a group either.
    """
    placeholders = [".localized", "account", "data", "l", "sessions", "sign-in"]
    for name in placeholders:
        write(tmp_path / name, b"")

    # Also add a real duplicate pair to make sure those still surface.
    real_data = b"real content" * 500
    write(tmp_path / "doc_a.pdf", real_data)
    write(tmp_path / "doc_b.pdf", real_data)

    groups = normalise(scan(str(tmp_path)))

    # Only the real duplicate pair must be reported - not a single placeholder.
    assert groups == {(str(tmp_path / "doc_a.pdf"), str(tmp_path / "doc_b.pdf"))}


@pytest.mark.skipif(os.name == "nt", reason="symlinks need privileges on Windows")
def test_symlink_mixed_with_real_file_same_content(tmp_path):
    """A symlink that points at a file with the same content must not create a
    false duplicate group.

    Without this guard a user could be prompted to delete the symlink target,
    leaving the link dangling - or worse, prompted to delete the symlink while
    believing it is a full independent copy that wastes space.
    """
    real_data = b"important payload" * 1000
    real = write(tmp_path / "original.bin", real_data)
    # Symlink resolves to the same bytes, but is NOT a copy.
    os.symlink(real, tmp_path / "link.bin")
    # Unrelated duplicate pair that must still be detected.
    extra = b"other data" * 500
    write(tmp_path / "extra_a.bin", extra)
    write(tmp_path / "extra_b.bin", extra)

    groups = normalise(scan(str(tmp_path)))
    paths_in_groups = {p for g in groups for p in g}

    # Symlink must never appear in any group.
    assert str(tmp_path / "link.bin") not in paths_in_groups
    # Real duplicate pair must be found.
    assert (str(tmp_path / "extra_a.bin"), str(tmp_path / "extra_b.bin")) in groups
    # original.bin has no duplicate (only its symlink shares the bytes, and
    # symlinks are excluded), so it must not appear in any group either.
    assert str(tmp_path / "original.bin") not in paths_in_groups


@pytest.mark.skipif(os.name == "nt", reason="hardlinks need privileges on Windows")
def test_hardlinks_are_reported_and_read_once(tmp_path):
    data = os.urandom(200000)
    src = write(tmp_path / "a.bin", data)
    link = tmp_path / "b.bin"
    os.link(src, link)
    other = write(tmp_path / "c.bin", data)

    hm, stats, _ = asyncio.run(find_duplicates_detailed_async(str(tmp_path)))
    assert normalise(hm) == {(str(src), str(link), str(other))}
    # Three paths, but only two distinct inodes were ever read.
    assert stats.hardlinks_collapsed == 1


def test_unique_size_files_are_never_opened(tmp_path):
    for i in range(20):
        write(tmp_path / f"f{i}.bin", b"x" * (i + 1))
    hm, stats, _ = asyncio.run(find_duplicates_detailed_async(str(tmp_path)))
    assert hm == {}
    assert stats.skipped_by_size == 20
    assert stats.fully_hashed == 0
    assert stats.bytes_read == 0


def test_min_size_filter(tmp_path):
    write(tmp_path / "small_a.bin", b"ab")
    write(tmp_path / "small_b.bin", b"ab")
    big = b"y" * 5000
    write(tmp_path / "big_a.bin", big)
    write(tmp_path / "big_b.bin", big)
    groups = normalise(scan(str(tmp_path), min_size=1000))
    assert groups == {(str(tmp_path / "big_a.bin"), str(tmp_path / "big_b.bin"))}


# --------------------------------------------------------------------------
# Zip content matching must survive size bucketing
# --------------------------------------------------------------------------


def test_single_loose_file_matches_zip_content(tmp_path):
    """One plain file plus one zip.

    The plain file has a unique on-disk size, so a naive size filter would drop
    it before ever comparing it with the zip's decompressed contents.
    """
    data = b"payload" * 900
    write(tmp_path / "loose.txt", data)
    z = tmp_path / "pack.zip"
    with zipfile.ZipFile(z, "w", compression=zipfile.ZIP_STORED) as zf:
        zf.writestr("inner.txt", data)

    assert normalise(scan(str(tmp_path))) == {tuple(sorted([str(z), str(tmp_path / "loose.txt")]))}


def test_compressed_zip_matches_loose_file(tmp_path):
    """Deflate makes the zip much smaller on disk than its contents."""
    data = b"compressible " * 5000
    write(tmp_path / "loose.txt", data)
    z = tmp_path / "pack.zip"
    with zipfile.ZipFile(z, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("inner.txt", data)
    assert z.stat().st_size < len(data) / 2
    assert normalise(scan(str(tmp_path))) == {tuple(sorted([str(z), str(tmp_path / "loose.txt")]))}


# --------------------------------------------------------------------------
# Verification, caching and progress
# --------------------------------------------------------------------------


def test_verify_mode_agrees_with_hashing(tmp_path):
    data = os.urandom(150000)
    write(tmp_path / "a.bin", data)
    write(tmp_path / "b.bin", data)
    write(tmp_path / "c.bin", os.urandom(150000))
    assert normalise(scan(str(tmp_path), verify=True)) == normalise(scan(str(tmp_path)))


def test_cache_is_invalidated_when_file_changes(tmp_path):
    a = write(tmp_path / "a.bin", b"same" * 5000)
    write(tmp_path / "b.bin", b"same" * 5000)
    assert len(normalise(scan(str(tmp_path)))) == 1

    a.write_bytes(b"diff" * 5000)
    os.utime(a, ns=(1, 2))
    assert scan(str(tmp_path)) == {}


def test_progress_is_monotonic_and_covers_every_file(tmp_path):
    data = os.urandom(90000)
    for i in range(6):
        write(tmp_path / f"dup{i}.bin", data)
    for i in range(6):
        write(tmp_path / f"uniq{i}.bin", os.urandom(1000 + i))

    calls = []
    asyncio.run(find_duplicates_by_hash_async(str(tmp_path), lambda i, t: calls.append((i, t))))

    assert len(calls) == 12
    assert [c[0] for c in calls] == list(range(1, 13))
    assert all(c[1] == 12 for c in calls)


def test_workers_setting_does_not_change_result(tmp_path):
    for g in range(5):
        data = os.urandom(80000)
        for c in range(3):
            write(tmp_path / f"g{g}" / f"c{c}.bin", data)
    expected = normalise(scan(str(tmp_path)))
    for w in (1, 2, 16):
        clear_hash_cache()
        assert normalise(scan(str(tmp_path), workers=w)) == expected


# --------------------------------------------------------------------------
# Differential test against brute force
# --------------------------------------------------------------------------


def build_adversarial_tree(root, rnd: random.Random) -> None:
    """A tree designed to defeat every shortcut in the pipeline."""
    shared_head = bytes(rnd.getrandbits(8) for _ in range(70000))
    shared_tail = bytes(rnd.getrandbits(8) for _ in range(9000))

    for i in range(rnd.randint(2, 5)):
        # Same head and same tail, different middles.
        middle = bytes([rnd.randrange(256)]) * 30000
        write(root / "headtail" / f"f{i}.bin", shared_head + middle + shared_tail)

    # Genuine duplicates at several sizes.
    for g in range(rnd.randint(1, 4)):
        # size=0 is intentionally excluded: zero-byte files are skipped by
        # the real scanner (safety gate) and by brute_force(), so they would
        # always produce a false mismatch in the differential test.
        size = rnd.choice([1, 5000, 70000, 200000])
        data = bytes(rnd.getrandbits(8) for _ in range(size))
        for c in range(rnd.randint(2, 4)):
            write(root / f"dup{g}" / f"c{c}.bin", data)

    # Same size, different content.
    size = 80000
    for i in range(3):
        write(root / "samesize" / f"s{i}.bin", bytes([i]) * size)

    # Unique files.
    for i in range(rnd.randint(0, 5)):
        n = rnd.randrange(1, 50000)
        write(root / "uniq" / f"u{i}.bin", bytes(rnd.getrandbits(8) for _ in range(n)))

    # A zip whose contents match a loose file.
    payload = bytes(rnd.getrandbits(8) for _ in range(rnd.randrange(100, 20000)))
    write(root / "loose" / "match.bin", payload)
    zpath = root / "zips" / "p.zip"
    zpath.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zpath, "w", compression=zipfile.ZIP_STORED) as zf:
        zf.writestr("inner.bin", payload)


@pytest.mark.parametrize("seed", list(range(12)))
def test_staged_matches_brute_force(tmp_path, seed):
    rnd = random.Random(seed)
    build_adversarial_tree(tmp_path, rnd)

    expected = normalise(brute_force(str(tmp_path)))
    clear_hash_cache()
    assert normalise(scan(str(tmp_path))) == expected
    clear_hash_cache()
    assert normalise(scan(str(tmp_path), verify=True)) == expected
    clear_hash_cache()
    assert normalise(scan(str(tmp_path), workers=1)) == expected


# --------------------------------------------------------------------------
# Symlinks
# --------------------------------------------------------------------------


@pytest.mark.skipif(os.name == "nt", reason="symlinks need privileges on Windows")
def test_symlinks_are_not_reported_as_duplicates(tmp_path):
    """A symlink is not a second copy.

    Reporting one would invite deleting a link whose target is the only real
    file, and it frees no space. fdupes, rdfind and fclones all skip them.
    """
    target = write(tmp_path / "real.bin", b"payload" * 2000)
    os.symlink(target, tmp_path / "link.bin")
    assert scan(str(tmp_path)) == {}


@pytest.mark.skipif(os.name == "nt", reason="symlinks need privileges on Windows")
def test_symlinks_can_be_followed_on_request(tmp_path):
    target = write(tmp_path / "real.bin", b"payload" * 2000)
    link = tmp_path / "link.bin"
    os.symlink(target, link)
    groups = normalise(scan(str(tmp_path), follow_symlinks=True))
    assert groups == {tuple(sorted([str(target), str(link)]))}


@pytest.mark.skipif(os.name == "nt", reason="symlinks need privileges on Windows")
def test_symlinked_directory_loop_terminates(tmp_path):
    d = tmp_path / "sub"
    d.mkdir()
    write(d / "a.bin", b"x" * 100)
    os.symlink(tmp_path, d / "loop")
    # Must not recurse forever.
    scan(str(tmp_path), follow_symlinks=True)
