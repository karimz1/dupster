import asyncio
import hashlib
import os
import zipfile
from typing import Optional

BLOCK_SIZE = 65536


def compute_file_hash(path: str, block_size: int = BLOCK_SIZE) -> Optional[str]:
    hasher = hashlib.sha256()
    try:
        with open(path, "rb") as f:
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


async def compute_hash_async(path: str) -> Optional[str]:
    ext = os.path.splitext(path)[1].lower()
    if ext == ".zip":
        return await asyncio.to_thread(compute_zip_content_hash, path)
    return await asyncio.to_thread(compute_file_hash, path)
