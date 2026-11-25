"""Local settings in config.json next to the app: the saved email and the review's work folder.

The file is outside git. Each function takes the path so tests can point to a temporary file.
"""

import json
import logging
import os
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

_BASE = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).parent
CONFIG_FILE = _BASE / "config.json"

_WORK_FOLDER = "work_folder"


def read(path: Path = CONFIG_FILE) -> dict:
    """config.json as a dict; missing, unreadable or non-object content counts as empty."""
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        logger.warning("Could not read %s", path, exc_info=True)
        return {}
    return data if isinstance(data, dict) else {}


def write(data: dict, path: Path = CONFIG_FILE) -> None:
    """Replaces config.json in one step, so a failure halfway never leaves it cut off (it holds the email).

    If the replace fails (on Windows, while another program holds the file), the temporary file is removed:
    it also holds the email and, in development, sits next to the code of a public repo.
    """
    partial = path.with_name(path.name + ".tmp")
    try:
        partial.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        os.replace(partial, path)
    except BaseException:
        partial.unlink(missing_ok=True)
        raise


def work_folder(path: Path = CONFIG_FILE) -> Path | None:
    """The folder chosen for the review, or None. It may no longer exist: the caller decides what to say."""
    value = read(path).get(_WORK_FOLDER)
    return Path(value) if isinstance(value, str) and value else None


def set_work_folder(folder: Path, path: Path = CONFIG_FILE) -> None:
    data = read(path)
    data[_WORK_FOLDER] = str(folder)
    write(data, path)
