#!/usr/bin/env python3
import hashlib
import os
import random
import shutil
from datetime import datetime
from pathlib import Path
import zipfile
import typer


app = typer.Typer(help="Generate a local dataset of duplicate/unique files for Dupster demos.", add_completion=False)


def _content_for_group(group: int, size_kb: int) -> bytes:
    rnd = random.Random(group)
    chunk = bytearray(1024)
    for i in range(1024):
        chunk[i] = rnd.randrange(0, 256)
    return bytes(chunk) * size_kb


def _write(path: Path, data: bytes) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


@app.command()
def main(
    root: Path = typer.Option(None, help="Target root directory under repo (e.g., temp/dataset)", dir_okay=True, file_okay=False),
    groups: int = typer.Option(3, min=1, help="Number of duplicate groups"),
    copies: int = typer.Option(3, min=2, help="Copies per duplicate group"),
    size_kb: int = typer.Option(64, min=1, help="Approx size per file in KB"),
    unique: int = typer.Option(2, min=0, help="Number of unique files to generate"),
    same_name_pairs: int = typer.Option(1, min=0, help="Pairs of same filename with different content"),
    include_zip: bool = typer.Option(True, help="Include a ZIP that contains duplicate content"),
    clean: bool = typer.Option(False, help="If target exists, delete it first"),
):
    repo_root = Path(__file__).resolve().parents[1]
    if root is None:
        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        root = repo_root / "temp" / f"dupster_dataset-{ts}"
    else:
        if not root.is_absolute():
            root = repo_root / root

    if root.exists() and clean:
        shutil.rmtree(root)
    root.mkdir(parents=True, exist_ok=True)

    # Duplicate groups
    for g in range(1, groups + 1):
        data = _content_for_group(g, size_kb)
        for c in range(1, copies + 1):
            _write(root / f"group{g}" / f"copy{c}.bin", data)
        if include_zip and g == 1:
            z = root / f"group{g}" / "dupe.zip"
            with zipfile.ZipFile(z, "w", compression=zipfile.ZIP_STORED) as zipf:
                zipf.writestr("inside.bin", data)

    # Unique files
    for i in range(unique):
        data = _content_for_group(1000 + i, size_kb // 2 if size_kb > 1 else 1)
        _write(root / "unique" / f"unique{i+1}.bin", data)

    # Same filename, different content
    for i in range(same_name_pairs):
        base = f"same_name_{i+1}.txt"
        _write(root / "same-name-1" / base, _content_for_group(2000 + i, 1))
        _write(root / "same-name-2" / base, _content_for_group(3000 + i, 1))

    typer.echo(str(root))


if __name__ == "__main__":
    app()
