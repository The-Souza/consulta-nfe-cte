"""The review progress in entrada/.conferencia.json, so closing and reopening the app resumes the review.

Only data is kept, never images: the crops are rebuilt when a photo is opened. A missing, broken or
other-version file never stops the screen: the photos are simply read again.
"""

import ctypes
import hashlib
import json
import logging
import os
import sys
from collections.abc import Iterable
from datetime import date, datetime
from pathlib import Path

from conference.photo import Photo, SystemInfo

logger = logging.getLogger(__name__)

FILE_NAME = ".conferencia.json"
VERSION = 1
_HIDDEN = 0x2  # FILE_ATTRIBUTE_HIDDEN
_CHUNK = 1 << 20


def file_hash(path: Path) -> str:
    """SHA-1 of the content: a photo whose bytes changed is read again."""
    digest = hashlib.sha1()
    with path.open("rb") as file:
        while chunk := file.read(_CHUNK):
            digest.update(chunk)
    return digest.hexdigest()


def _iso(value: date | None) -> str | None:
    return value.isoformat() if value is not None else None


def _to_json(photo: Photo) -> dict:
    system = photo.system
    return {
        "file_hash": photo.file_hash,
        "nfe": photo.nfe,
        "nfe_source": photo.nfe_source,
        "rotation": photo.rotation,
        "typed_date": _iso(photo.typed_date),
        "confirmed": photo.confirmed,
        "system": None if system is None else {
            "state": system.state,
            "delivery": _iso(system.delivery),
            "checked_at": system.checked_at.isoformat(),
            "status": system.status,
        },
        "date_box": list(photo.date_box) if photo.date_box is not None else None,
        "sharpness": photo.sharpness,
    }


def _date(value: str | None) -> date | None:
    return date.fromisoformat(value) if value is not None else None


def _from_json(name: str, entry: dict) -> Photo:
    raw_system = entry["system"]
    system = None if raw_system is None else SystemInfo(
        state=raw_system["state"],
        delivery=_date(raw_system["delivery"]),
        checked_at=datetime.fromisoformat(raw_system["checked_at"]),
        status=raw_system["status"],
    )
    box = entry["date_box"]
    return Photo(
        name=name,
        file_hash=entry["file_hash"],
        nfe=entry["nfe"],
        nfe_source=entry["nfe_source"],
        rotation=entry["rotation"],
        typed_date=_date(entry["typed_date"]),
        confirmed=entry["confirmed"],
        system=system,
        date_box=(box[0], box[1]) if box is not None else None,
        sharpness=entry["sharpness"],
    )


def load(folder: Path) -> dict[str, Photo]:
    """The saved photos by name. Anything unusable counts as no progress; a broken entry is skipped."""
    path = folder / FILE_NAME
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        logger.warning("Could not read %s; the photos are read again", path, exc_info=True)
        return {}
    if not isinstance(data, dict) or data.get("version") != VERSION or not isinstance(data.get("photos"), dict):
        logger.warning("Ignoring %s: not a version %s progress file", path, VERSION)
        return {}
    photos = {}
    for name, entry in data["photos"].items():
        try:
            photos[name] = _from_json(name, entry)
        except (KeyError, TypeError, ValueError, IndexError):
            logger.warning("Ignoring the saved progress of %s in %s", name, path, exc_info=True)
    return photos


def _hide(path: Path) -> None:
    # Replacing a hidden file drops the attribute, so it is set again on every save.
    if sys.platform == "win32" and not ctypes.windll.kernel32.SetFileAttributesW(str(path), _HIDDEN):
        logger.debug("Could not hide %s", path)


def save(folder: Path, photos: Iterable[Photo]) -> None:
    """Writes the progress in one step: a failure halfway leaves the previous file and no temporary."""
    path = folder / FILE_NAME
    partial = path.with_name(path.name + ".tmp")
    data = {"version": VERSION, "photos": {p.name: _to_json(p) for p in photos if not p.discarded}}
    try:
        partial.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
        os.replace(partial, path)
    except BaseException:
        partial.unlink(missing_ok=True)
        raise
    _hide(path)


def reconcile(saved: dict[str, Photo], files: Iterable[Path]) -> tuple[list[Photo], list[Path]]:
    """Splits the photos in entrada/ into those whose saved progress still holds (same content) and those to
    read again (new or changed). Saved photos no longer in the folder are dropped."""
    reuse, read = [], []
    for path in files:
        photo = saved.get(path.name)
        if photo is not None and photo.file_hash == file_hash(path):
            reuse.append(photo)
        else:
            read.append(path)
    return reuse, read
