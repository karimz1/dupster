import os
from dataclasses import dataclass


@dataclass
class DuplicateGroup:
    hash: str
    files: list[str]
    index: int

    def potential_savings(self) -> int:
        try:
            sizes = [os.path.getsize(f) for f in self.files]
            return sum(sizes) - max(sizes)
        except Exception:
            return 0
