from dataclasses import dataclass
from typing import List
import os


@dataclass
class DuplicateGroup:
    hash: str
    files: List[str]
    index: int

    def potential_savings(self) -> int:
        try:
            sizes = [os.path.getsize(f) for f in self.files]
            return sum(sizes) - max(sizes)
        except Exception:
            return 0

