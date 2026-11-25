"""File helpers shared by the upload steps: stub photos are only ever moved or copied, never overwritten."""

from pathlib import Path


def free_path(path: Path) -> Path:
    """`path`, or `name (2).ext`, `name (3).ext`... when it already exists. Never overwrites."""
    candidate, n = path, 2
    while candidate.exists():
        candidate = path.with_name(f"{path.stem} ({n}){path.suffix}")
        n += 1
    return candidate
