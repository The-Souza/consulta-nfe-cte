"""The work folder of the review: photos go into entrada/, discarded ones to descartadas/.

Nothing is ever deleted or overwritten: photos are copied in and moved out.
"""

import shutil
from collections.abc import Iterable
from pathlib import Path

from utils.files import free_path

INPUT_FOLDER = "entrada"
DISCARDED_FOLDER = "descartadas"
PHOTO_EXTENSIONS = (".jpg", ".jpeg", ".png")


def snapshot(paths: Iterable[Path]) -> dict[str, tuple[int, int]]:
    """Name → (size, modification time) of each photo: a cheap way to tell whether entrada/ changed
    without hashing every file. A file gone since the listing is left out."""
    result = {}
    for path in paths:
        try:
            stat = path.stat()
        except OSError:
            continue
        result[path.name] = (stat.st_size, stat.st_mtime_ns)
    return result


def work_root(picked: Path) -> Path:
    """The work folder for a folder the user picked: picking entrada/ itself means the folder above it, so
    the photos are not looked for in entrada/entrada/."""
    return picked.parent if picked.name.casefold() == INPUT_FOLDER else picked


class WorkFolder:
    def __init__(self, root: Path):
        self.root = root
        self.inputs_dir = root / INPUT_FOLDER
        self.discarded_dir = root / DISCARDED_FOLDER

    def ensure(self) -> None:
        """Creates the subfolders that are missing."""
        for folder in (self.inputs_dir, self.discarded_dir):
            folder.mkdir(parents=True, exist_ok=True)

    def inputs(self) -> list[Path]:
        """The photos in entrada/, without subfolders, in name order ignoring case."""
        if not self.inputs_dir.is_dir():
            return []
        photos = [p for p in self.inputs_dir.iterdir() if p.is_file() and p.suffix.lower() in PHOTO_EXTENSIONS]
        return sorted(photos, key=lambda p: p.name.casefold())

    def copy_in(self, sources: Iterable[Path]) -> list[Path]:
        """Copies photos into entrada/ (the originals stay where they were) and returns the new paths.

        A photo already in entrada/ is skipped instead of being copied next to itself.
        """
        copied = []
        for source in sources:
            if source.parent.resolve() == self.inputs_dir.resolve():
                continue
            target = free_path(self.inputs_dir / source.name)
            shutil.copy2(source, target)
            copied.append(target)
        return copied

    def discard(self, name: str) -> Path:
        """Moves a photo from entrada/ to descartadas/ and returns where it went."""
        source = self.inputs_dir / name
        if not source.is_file():
            raise FileNotFoundError(source)
        self.discarded_dir.mkdir(parents=True, exist_ok=True)
        target = free_path(self.discarded_dir / name)
        shutil.move(str(source), str(target))
        return target
