import os
from dataclasses import dataclass


@dataclass
class FileEntry:
    """A file discovered during the walk, with the stat data gathered in the same syscall."""

    path: str
    size: int
    dev: int
    ino: int
    mtime_ns: int = 0
    nlink: int = 1
    is_zip: bool = False

    @property
    def inode_key(self) -> tuple:
        """Identifies the physical data behind this path. Hardlinks share it."""
        return (self.dev, self.ino)

    @property
    def cache_key(self) -> tuple:
        """Identity for the hash cache. Any edit changes size or mtime."""
        return (self.dev, self.ino, self.size, self.mtime_ns)


@dataclass
class DuplicateGroup:
    hash: str
    files: list[str]
    index: int
    size: int = 0

    def potential_savings(self) -> int:
        # Every file in a group is byte-identical, so the size of one is enough.
        # The scanner already knows it, which avoids re-stating on every UI refresh.
        if self.size > 0:
            return self.size * max(len(self.files) - 1, 0)
        try:
            sizes = [os.path.getsize(f) for f in self.files]
            return sum(sizes) - max(sizes)
        except Exception:
            return 0
