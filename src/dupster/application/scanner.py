from collections import defaultdict
from typing import Callable, Optional

from dupster.infrastructure.filesystem import list_files
from dupster.infrastructure.hashing import compute_hash_async

ProgressCb = Optional[Callable[[int, int], None]]


async def find_duplicates_by_hash_async(
    folder: str, progress_cb: ProgressCb = None
) -> dict[str, list[str]]:
    files = list_files(folder)
    files.sort(key=lambda p: p.split("/")[-1].lower())
    total = len(files)
    by_hash: dict[str, list[str]] = defaultdict(list)
    for idx, path in enumerate(files, start=1):
        digest = await compute_hash_async(path)
        if digest:
            by_hash[digest].append(path)
        if progress_cb:
            try:
                progress_cb(idx, total)
            except Exception:
                pass
    return {h: ps for h, ps in by_hash.items() if len(ps) > 1}
