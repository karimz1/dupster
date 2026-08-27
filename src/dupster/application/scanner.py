"""Staged duplicate detection.

The cost of finding duplicates is dominated by reading bytes off disk, not by
hashing them (SHA-256 is hardware accelerated on any current CPU and runs at
gigabytes per second). So the pipeline is built to read as little as possible,
in the order the hardware likes best:

  stage 1  group by size .................. 0 bytes read
  stage 2  collapse hardlinked inodes ..... 0 bytes read
  stage 3  probe the first 4 KiB .......... 4 KiB per file
  stage 4  probe the middle and last 4 KiB . 8 KiB per file
  stage 5  full SHA-256 .................... survivors only
  stage 6  byte-for-byte compare ........... only with verify=True

A file is only ever fully read once it has survived every cheap test, and a
file whose size is unique in the tree is never opened at all.
"""

import asyncio
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Callable, Optional

from dupster.domain.models import FileEntry
from dupster.infrastructure.device import default_workers, detect_device_type
from dupster.infrastructure.filesystem import scan_entries
from dupster.infrastructure.hashing import (
    EDGE_MIN_SIZE,
    PROBE_MIN_SIZE,
    bytewise_split,
    compute_edge_hash,
    compute_file_hash,
    compute_head_hash,
    compute_zip_content_hash,
    zip_content_size,
)

ProgressCb = Optional[Callable[[int, int], None]]

# Digests survive across scans within a process. The TUI re-scans after every
# delete, and without this each delete re-reads the entire tree.
_HASH_CACHE: dict = {}
_CACHE_LIMIT = 250_000

# How many jobs are in flight per device before we wait.
_CHUNK = 2048


@dataclass
class ScanStats:
    files_seen: int = 0
    skipped_by_size: int = 0
    skipped_by_probe: int = 0
    hardlinks_collapsed: int = 0
    fully_hashed: int = 0
    cache_hits: int = 0
    bytes_read: int = 0
    elapsed: float = 0.0
    devices: dict = field(default_factory=dict)

    @property
    def files_opened(self) -> int:
        return self.files_seen - self.skipped_by_size


def clear_hash_cache() -> None:
    _HASH_CACHE.clear()


class _Progress:
    """Reports one tick per discovered file, at the moment it is resolved.

    "Resolved" means the file has reached a terminal state: eliminated by size,
    eliminated by a probe, or fully hashed. Ticks always run on the event loop,
    never on a pool thread, because the TUI callback mutates a widget directly.
    """

    def __init__(self, cb: ProgressCb, total: int):
        self._cb = cb
        self.total = total
        self.done = 0

    def resolve(self, n: int = 1) -> None:
        for _ in range(n):
            self.done += 1
            if self._cb:
                try:
                    self._cb(self.done, self.total)
                except Exception:
                    pass

    def finish(self) -> None:
        if self.done < self.total:
            self.resolve(self.total - self.done)


async def _map_device(
    fn: Callable,
    entries: list,
    executor: ThreadPoolExecutor,
    progress: Optional[_Progress] = None,
) -> list:
    """Run `fn` over `entries` on one device's pool, results paired with input.

    Work is submitted in bounded chunks so a tree with millions of files does
    not materialise millions of futures at once.
    """
    loop = asyncio.get_event_loop()
    out = []
    for start in range(0, len(entries), _CHUNK):
        chunk = entries[start : start + _CHUNK]
        futures = [loop.run_in_executor(executor, fn, item) for item in chunk]
        for item, result in zip(chunk, await asyncio.gather(*futures)):
            out.append((item, result))
    return out


def _by_device(entries: list) -> dict:
    groups: dict = defaultdict(list)
    for e in entries:
        groups[e.dev].append(e)
    return groups


async def _run_stage(
    fn: Callable,
    entries: list,
    device_plan: dict,
) -> list:
    """Fan `entries` out across every device, each with its own pool and order."""
    if not entries:
        return []

    async def run_one(dev: int, items: list) -> list:
        plan = device_plan[dev]
        # Elevator ordering. Reading in inode order approximates reading in
        # physical layout order, which turns a random seek storm on a spinning
        # disk into a single sweep. It is harmless on flash.
        items = sorted(items, key=lambda e: e.ino)
        with ThreadPoolExecutor(max_workers=plan["workers"]) as pool:
            return await _map_device(fn, items, pool)

    per_device = _by_device(entries)
    results = await asyncio.gather(*[run_one(dev, items) for dev, items in per_device.items()])
    return [pair for chunk in results for pair in chunk]


def _bucket_key_size(entry: FileEntry) -> int:
    return entry.size


def _collapse_inodes(entries: list) -> tuple:
    """Return (representatives, aliases) so shared inodes are read once.

    Hardlinks are literally the same bytes on disk. Reading each path would be
    pure waste, so one path per inode is read and the rest inherit its digest.
    """
    if not any(e.nlink > 1 for e in entries):
        return entries, {}
    reps: dict = {}
    aliases: dict = defaultdict(list)
    for e in entries:
        key = e.inode_key
        if key in reps:
            aliases[reps[key].path].append(e.path)
        else:
            reps[key] = e
    return list(reps.values()), dict(aliases)


def _full_digest(entry: FileEntry) -> Optional[str]:
    key = entry.cache_key
    cached = _HASH_CACHE.get(key)
    if cached is not None:
        return cached
    if entry.is_zip:
        digest = compute_zip_content_hash(entry.path)
    else:
        digest = compute_file_hash(entry.path)
    if digest is not None:
        if len(_HASH_CACHE) >= _CACHE_LIMIT:
            _HASH_CACHE.clear()
        _HASH_CACHE[key] = digest
    return digest


async def find_duplicates_detailed_async(
    folder: str,
    progress_cb: ProgressCb = None,
    workers: Optional[int] = None,
    min_size: int = 0,
    verify: bool = False,
    follow_symlinks: bool = False,
) -> tuple:
    """Find duplicates and report how the work was actually done."""
    started = time.perf_counter()
    stats = ScanStats()

    entries = await asyncio.to_thread(scan_entries, folder, follow_symlinks)
    stats.files_seen = len(entries)
    progress = _Progress(progress_cb, len(entries))

    # Plan I/O per physical device. A scan can span an NVMe and a USB drive at
    # once, and they want opposite strategies.
    device_plan: dict = {}
    for dev, items in _by_device(entries).items():
        dtype = detect_device_type(items[0].path, dev)
        device_plan[dev] = {
            "type": dtype,
            "workers": workers if workers and workers > 0 else default_workers(dtype),
        }
        stats.devices[dev] = device_plan[dev]

    # A zip is hashed by its decompressed contents, so it must be bucketed by
    # that size, not by its size on disk. The central directory has it already.
    candidates = []
    for e in entries:
        if e.size < min_size and not e.is_zip:
            progress.resolve()
            stats.skipped_by_size += 1
            continue
        if e.is_zip:
            content = zip_content_size(e.path)
            if content is not None:
                e = FileEntry(
                    path=e.path,
                    size=content,
                    dev=e.dev,
                    ino=e.ino,
                    mtime_ns=e.mtime_ns,
                    nlink=e.nlink,
                    is_zip=True,
                )
        candidates.append(e)

    # Stage 1: size. Anything with a unique size cannot have a twin.
    buckets: dict = defaultdict(list)
    for e in candidates:
        buckets[_bucket_key_size(e)].append(e)

    survivors: list = []
    alias_map: dict = {}
    zip_buckets: set = set()
    for size, group in buckets.items():
        if len(group) < 2:
            progress.resolve(len(group))
            stats.skipped_by_size += len(group)
            continue
        # Stage 2: one read per inode, hardlinks inherit the result.
        reps, aliases = _collapse_inodes(group)
        stats.hardlinks_collapsed += len(group) - len(reps)
        alias_map.update(aliases)
        if any(e.is_zip for e in reps):
            # Zip content cannot be probed the same way as raw bytes, so this
            # whole bucket skips to the authoritative hash.
            zip_buckets.add(size)
        survivors.extend(reps)

    def _alias_count(entry: FileEntry) -> int:
        return 1 + len(alias_map.get(entry.path, ()))

    def _path_count(group: list) -> int:
        """Paths represented by a group, counting collapsed hardlinks.

        A group can be a single representative that stands for several
        hardlinked paths. That is still a duplicate group, so survival must be
        judged on paths rather than on representatives.
        """
        return sum(_alias_count(e) for e in group)

    # Stage 3: head probe. Files small enough that a probe would read most of
    # them anyway go straight to the full hash.
    probeable = [
        e
        for e in survivors
        if e.size > PROBE_MIN_SIZE and not e.is_zip and e.size not in zip_buckets
    ]
    probe_set = {id(e) for e in probeable}
    direct = [e for e in survivors if id(e) not in probe_set]

    keyed: dict = defaultdict(list)
    for e in direct:
        keyed[(e.size,)].append(e)

    if probeable:
        head_results = await _run_stage(lambda e: compute_head_hash(e.path), probeable, device_plan)
        stats.bytes_read += len(probeable) * 4096
        head_groups: dict = defaultdict(list)
        for entry, digest in head_results:
            if digest is None:
                progress.resolve(_alias_count(entry))
                continue
            head_groups[(entry.size, digest)].append(entry)

        # Stage 4: middle and tail probe, for files big enough that a shared
        # header is plausible.
        edge_candidates = []
        for key, group in head_groups.items():
            if _path_count(group) < 2:
                for e in group:
                    progress.resolve(_alias_count(e))
                    stats.skipped_by_probe += _alias_count(e)
                continue
            for e in group:
                if e.size > EDGE_MIN_SIZE:
                    edge_candidates.append((key, e))
                else:
                    keyed[key].append(e)

        if edge_candidates:
            edge_entries = [e for _, e in edge_candidates]
            key_of = {id(e): k for k, e in edge_candidates}
            edge_results = await _run_stage(
                lambda e: compute_edge_hash(e.path, e.size), edge_entries, device_plan
            )
            stats.bytes_read += len(edge_entries) * 8192
            for entry, digest in edge_results:
                if digest is None:
                    progress.resolve(_alias_count(entry))
                    continue
                keyed[key_of[id(entry)] + (digest,)].append(entry)

    # Stage 5: the authoritative SHA-256, on whatever is left.
    finalists: list = []
    for group in keyed.values():
        if _path_count(group) < 2:
            for e in group:
                progress.resolve(_alias_count(e))
                stats.skipped_by_probe += _alias_count(e)
            continue
        finalists.extend(group)

    by_hash: dict = defaultdict(list)
    sizes: dict = {}
    zip_paths: set = set()
    if finalists:
        cached_keys = {e.cache_key for e in finalists if e.cache_key in _HASH_CACHE}
        stats.cache_hits += len(cached_keys)
        results = await _run_stage(_full_digest, finalists, device_plan)
        for entry, digest in results:
            stats.fully_hashed += 1
            if entry.cache_key not in cached_keys:
                stats.bytes_read += entry.size
            progress.resolve(_alias_count(entry))
            if not digest:
                continue
            by_hash[digest].append(entry.path)
            sizes[entry.path] = entry.size
            if entry.is_zip:
                zip_paths.add(entry.path)
            for alias in alias_map.get(entry.path, ()):
                by_hash[digest].append(alias)
                sizes[alias] = entry.size

    duplicates = {h: sorted(ps) for h, ps in by_hash.items() if len(ps) > 1}

    # Stage 6: optional proof by exact comparison. A SHA-256 group splitting
    # here would mean an actual collision, so in practice this only confirms.
    #
    # Groups containing a zip are left alone. Their members were matched on
    # decompressed content, so their raw bytes are legitimately different and
    # comparing those would wrongly tear the group apart.
    if verify and duplicates:
        verified: dict = {}
        for h, paths in duplicates.items():
            if any(p in zip_paths for p in paths):
                verified[h] = paths
                continue
            for i, group in enumerate(bytewise_split(paths)):
                key = h if i == 0 else f"{h}#{i + 1}"
                verified[key] = sorted(group)
        duplicates = {h: p for h, p in verified.items() if len(p) > 1}

    progress.finish()
    stats.elapsed = time.perf_counter() - started
    return duplicates, stats, sizes


async def find_duplicates_by_hash_async(
    folder: str,
    progress_cb: ProgressCb = None,
    workers: Optional[int] = None,
    min_size: int = 0,
    verify: bool = False,
    follow_symlinks: bool = False,
) -> dict:
    duplicates, _, _ = await find_duplicates_detailed_async(
        folder,
        progress_cb=progress_cb,
        workers=workers,
        min_size=min_size,
        verify=verify,
        follow_symlinks=follow_symlinks,
    )
    return duplicates
