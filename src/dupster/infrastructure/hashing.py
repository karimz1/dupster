import asyncio
import hashlib
import os
import sys
import zipfile
from typing import Optional

BLOCK_SIZE = 65536

# Bytes sampled per probe during the cheap filtering stages.
PROBE_SIZE = 4096
# Files at or below this never get probed: reading a probe would cost as much as
# reading the whole file, so we go straight to the authoritative hash.
PROBE_MIN_SIZE = 2 * PROBE_SIZE
# Above this a file also gets its middle and tail sampled.
EDGE_MIN_SIZE = 65536
# Block size for exact byte-for-byte comparison.
COMPARE_BLOCK = 262144


def _fast_hasher():
    """Hasher for the filtering stages.

    These digests never decide that two files are equal, they only decide that
    two files are *not* equal, so a fast non cryptographic digest is enough. A
    collision here costs one extra stage, never a wrong answer.
    """
    return hashlib.blake2b(digest_size=16)


def _advise_sequential(fd: int, length: int = 0) -> None:
    """Tell the kernel we are about to stream this file, best effort."""
    try:
        if hasattr(os, "posix_fadvise"):
            os.posix_fadvise(fd, 0, length, os.POSIX_FADV_SEQUENTIAL)
        elif sys.platform == "darwin":
            import fcntl

            # F_RDAHEAD = 45, turn on aggressive readahead.
            fcntl.fcntl(fd, 45, 1)
    except (OSError, AttributeError, ImportError):
        pass


def _advise_random(fd: int) -> None:
    try:
        if hasattr(os, "posix_fadvise"):
            os.posix_fadvise(fd, 0, 0, os.POSIX_FADV_RANDOM)
    except (OSError, AttributeError):
        pass


def compute_file_hash(path: str, block_size: int = BLOCK_SIZE) -> Optional[str]:
    hasher = hashlib.sha256()
    try:
        with open(path, "rb") as f:
            _advise_sequential(f.fileno())
            for chunk in iter(lambda: f.read(block_size), b""):
                hasher.update(chunk)
    except Exception:
        return None
    return hasher.hexdigest()


def compute_zip_content_hash(path: str, block_size: int = BLOCK_SIZE) -> Optional[str]:
    hasher = hashlib.sha256()
    try:
        with zipfile.ZipFile(path, "r") as z:
            names = sorted([n for n in z.namelist() if not n.endswith("/")])
            for name in names:
                with z.open(name) as f:
                    for chunk in iter(lambda: f.read(block_size), b""):
                        hasher.update(chunk)
    except Exception:
        return None
    return hasher.hexdigest()


def zip_content_size(path: str) -> Optional[int]:
    """Total uncompressed size of a zip, read from the central directory.

    Nothing is decompressed. This lets a zip take part in size bucketing on the
    same terms as the loose files its contents might match.
    """
    try:
        with zipfile.ZipFile(path, "r") as z:
            return sum(zi.file_size for zi in z.infolist() if not zi.is_dir())
    except Exception:
        return None


def compute_head_hash(path: str, probe: int = PROBE_SIZE) -> Optional[str]:
    """Digest of the first `probe` bytes."""
    try:
        with open(path, "rb") as f:
            _advise_random(f.fileno())
            data = f.read(probe)
    except Exception:
        return None
    h = _fast_hasher()
    h.update(data)
    return h.hexdigest()


def compute_edge_hash(path: str, size: int, probe: int = PROBE_SIZE) -> Optional[str]:
    """Digest of the middle and tail probes.

    The head is deliberately excluded because the previous stage already read
    it. Sampling the tail catches the very common case of files that share a
    long header (media containers, PDFs, disk images, log files) but diverge at
    the end, which a head-only filter would push into a full read.
    """
    h = _fast_hasher()
    try:
        with open(path, "rb") as f:
            _advise_random(f.fileno())
            mid = max((size // 2) - (probe // 2), 0)
            f.seek(mid)
            h.update(f.read(probe))
            tail = max(size - probe, 0)
            f.seek(tail)
            h.update(f.read(probe))
    except Exception:
        return None
    return h.hexdigest()


def bytewise_split(paths: list, block: int = COMPARE_BLOCK) -> list:
    """Split `paths` into groups that are byte-for-byte identical.

    This is the lockstep n-way comparison used by fdupes and jdupes: every
    candidate is read in parallel and the set splits the moment a block
    differs, so mismatched files stop being read early. Used for --verify,
    where it turns "astronomically unlikely to collide" into "proven equal".

    Grouping uses a dict keyed on the raw block, so equality is exact bytes,
    never a digest.
    """
    if len(paths) < 2:
        return []

    handles = {}
    try:
        for p in paths:
            try:
                fh = open(p, "rb")
                _advise_sequential(fh.fileno())
                handles[p] = fh
            except OSError:
                continue

        pending = [list(handles.keys())] if len(handles) > 1 else []
        done = []
        while pending:
            next_pending = []
            for group in pending:
                buckets: dict = {}
                for path in group:
                    try:
                        chunk = handles[path].read(block)
                    except OSError:
                        continue
                    buckets.setdefault(chunk, []).append(path)
                for chunk, members in buckets.items():
                    if len(members) < 2:
                        continue
                    if chunk == b"":
                        # Read to EOF in lockstep, so these are proven equal.
                        done.append(members)
                    else:
                        next_pending.append(members)
            pending = next_pending
        return done
    finally:
        for fh in handles.values():
            try:
                fh.close()
            except OSError:
                pass


async def compute_hash_async(path: str) -> Optional[str]:
    ext = os.path.splitext(path)[1].lower()
    if ext == ".zip":
        return await asyncio.to_thread(compute_zip_content_hash, path)
    return await asyncio.to_thread(compute_file_hash, path)
