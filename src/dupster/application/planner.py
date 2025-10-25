from typing import Dict, List

from dupster.domain.models import DuplicateGroup
from dupster.infrastructure.filesystem import get_size


def groups_from_hash_map(hm: Dict[str, List[str]]) -> List[DuplicateGroup]:
    items: List[DuplicateGroup] = []
    for i, (h, files) in enumerate(sorted(hm.items(), key=lambda kv: kv[0])):
        items.append(DuplicateGroup(hash=h, files=sorted(files), index=i + 1))
    return items


def keep_one_plan(group: DuplicateGroup, keep_path: str) -> dict:
    dels = [p for p in group.files if p != keep_path]
    return {"group": group.index, "hash": group.hash, "keep": keep_path, "delete": dels}


def bulk_delete_plan(groups: List[DuplicateGroup]) -> List[dict]:
    plan: List[dict] = []
    for g in groups:
        if not g.files:
            continue
        keep = sorted(g.files)[0]
        dels = [p for p in g.files if p != keep]
        if not dels:
            continue
        plan.append({"group": g.index, "hash": g.hash, "keep": keep, "delete": dels})
    return plan


def total_reclaim_bytes(plan: List[dict]) -> int:
    try:
        return sum(get_size(p) for entry in plan for p in entry["delete"])
    except Exception:
        return 0

