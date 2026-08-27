#!/usr/bin/env python3
"""Compare the staged scanner against the old hash-everything approach.

    python tools/benchmark.py --generate temp/bench
    python tools/benchmark.py ~/Downloads
"""

import argparse
import asyncio
import os
import random
import shutil
import sys
import time
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from dupster.application.scanner import (  # noqa: E402
    clear_hash_cache,
    find_duplicates_detailed_async,
)
from dupster.infrastructure.filesystem import iter_entries  # noqa: E402
from dupster.infrastructure.hashing import (  # noqa: E402
    compute_file_hash,
    compute_zip_content_hash,
)


def legacy_scan(root: str):
    """The previous algorithm: full SHA-256 of every file, one at a time."""
    by_hash = {}
    total_bytes = 0
    paths = []
    for r, _, files in os.walk(root):
        for name in files:
            p = os.path.join(r, name)
            # Symlinks are skipped so this compares like for like with the
            # staged scanner, which never follows them by default.
            if os.path.isfile(p) and not os.path.islink(p):
                paths.append(p)
    paths.sort(key=lambda p: p.split("/")[-1].lower())
    for p in paths:
        if p.lower().endswith(".zip"):
            digest = compute_zip_content_hash(p)
        else:
            digest = compute_file_hash(p)
        try:
            total_bytes += os.path.getsize(p)
        except OSError:
            pass
        if digest:
            by_hash.setdefault(digest, []).append(p)
    return {h: sorted(v) for h, v in by_hash.items() if len(v) > 1}, total_bytes, len(paths)


def generate(root: Path, files: int, seed: int = 7) -> None:
    """Build a corpus shaped like a real directory tree.

    Mostly unique files at a realistic spread of sizes, a minority of genuine
    duplicates, plus shared-header files that only a tail probe can separate.
    """
    rnd = random.Random(seed)
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True)

    # Size distribution roughly like a home directory: lots of small files,
    # a long tail of large ones.
    def pick_size() -> int:
        r = rnd.random()
        if r < 0.55:
            return rnd.randrange(200, 20_000)
        if r < 0.85:
            return rnd.randrange(20_000, 400_000)
        if r < 0.98:
            return rnd.randrange(400_000, 4_000_000)
        return rnd.randrange(4_000_000, 20_000_000)

    shared_header = os.urandom(80_000)
    written = 0
    dup_payloads = []

    while written < files:
        d = root / f"dir{rnd.randrange(60)}" / f"sub{rnd.randrange(12)}"
        d.mkdir(parents=True, exist_ok=True)
        roll = rnd.random()

        if roll < 0.15 and dup_payloads:
            # A real duplicate of something already written.
            data = rnd.choice(dup_payloads)
        elif roll < 0.25:
            # Shares a long header with its siblings but differs at the end.
            size = pick_size()
            body = os.urandom(max(size - len(shared_header), 1))
            data = shared_header + body
        else:
            size = pick_size()
            data = os.urandom(size)
            if rnd.random() < 0.1 and len(dup_payloads) < 60:
                dup_payloads.append(data)

        (d / f"f{written}.bin").write_bytes(data)
        written += 1

    # A couple of zips whose contents match loose files.
    zdir = root / "archives"
    zdir.mkdir(parents=True, exist_ok=True)
    for i, payload in enumerate(dup_payloads[:3]):
        with zipfile.ZipFile(zdir / f"a{i}.zip", "w", compression=zipfile.ZIP_STORED) as zf:
            zf.writestr("inner.bin", payload)


def human(n: float) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(n) < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} PB"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("path", nargs="?", help="Directory to scan")
    ap.add_argument("--generate", metavar="DIR", help="Generate a corpus here first")
    ap.add_argument("--files", type=int, default=8000, help="Files to generate")
    ap.add_argument("--skip-legacy", action="store_true")
    args = ap.parse_args()

    if args.generate:
        target = Path(args.generate)
        print(f"generating {args.files} files in {target} ...")
        generate(target, args.files)
        root = str(target)
    elif args.path:
        root = os.path.expanduser(args.path)
    else:
        ap.error("give a path or --generate DIR")

    total = sum(1 for _ in iter_entries(root))
    print(f"\ncorpus: {root}  ({total:,} files)\n")

    legacy_result = None
    legacy_elapsed = 0.0
    if not args.skip_legacy:
        t0 = time.perf_counter()
        legacy_result, legacy_bytes, legacy_files = legacy_scan(root)
        legacy_elapsed = time.perf_counter() - t0
        print("old  full SHA-256 of every file, sequential")
        print(f"     time        {legacy_elapsed:8.2f} s")
        print(f"     read        {human(legacy_bytes):>10}")
        print(f"     groups      {len(legacy_result):8,}\n")

    clear_hash_cache()
    t0 = time.perf_counter()
    new_result, stats, _ = asyncio.run(find_duplicates_detailed_async(root))
    new_elapsed = time.perf_counter() - t0

    print("new  staged pipeline")
    print(f"     time        {new_elapsed:8.2f} s")
    print(f"     read        {human(stats.bytes_read):>10}")
    print(f"     groups      {len(new_result):8,}")
    print(f"     skipped by size      {stats.skipped_by_size:8,}")
    print(f"     skipped by probe     {stats.skipped_by_probe:8,}")
    print(f"     fully hashed         {stats.fully_hashed:8,}")
    print(f"     hardlinks collapsed  {stats.hardlinks_collapsed:8,}")
    print(f"     devices              {[d['type'] for d in stats.devices.values()]}")

    t0 = time.perf_counter()
    asyncio.run(find_duplicates_detailed_async(root))
    cached_elapsed = time.perf_counter() - t0
    print(f"\n     rescan (warm cache)  {cached_elapsed:8.2f} s")

    if legacy_result is not None:
        same = {tuple(sorted(v)) for v in legacy_result.values()} == {
            tuple(sorted(v)) for v in new_result.values()
        }
        print(f"\nidentical results: {same}")
        if not same:
            print("MISMATCH, results differ")
            sys.exit(1)
        if new_elapsed > 0:
            print(f"speedup:           {legacy_elapsed / new_elapsed:.1f}x")
            print(f"bytes read:        {legacy_bytes / max(stats.bytes_read, 1):.1f}x less")


if __name__ == "__main__":
    main()
