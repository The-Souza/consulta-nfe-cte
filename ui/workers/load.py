import logging
from collections.abc import Sequence
from pathlib import Path
from typing import Callable

import image_pipeline
from conference.photo import Photo
from conference.progress import file_hash, reconcile

logger = logging.getLogger(__name__)


def _read(path: Path) -> Photo:
    """Any failure leaves the photo unread, for the number to be typed, instead of dropping it."""
    try:
        digest = file_hash(path)
    except OSError:
        logger.warning("Could not hash %s; it is read again next time", path.name, exc_info=True)
        # An empty hash never matches, so the next load reads the photo again.
        digest = ""
    try:
        result = image_pipeline.process(path)
    except Exception:
        logger.exception("Could not read %s", path.name)
        return Photo(path.name, digest)
    return Photo(
        path.name,
        digest,
        nfe=result.nfe,
        nfe_source=result.nfe_source,
        rotation=result.rotation,
        sharpness=result.sharpness,
    )


class LoadWorker:
    """Reuses the saved photos that did not change and reads the new or changed ones with the pipeline."""

    def __init__(
        self,
        files: Sequence[Path],
        saved: dict[str, Photo],
        stop_event,
        after_fn: Callable,
        on_known: Callable[[list[Photo]], None],
        on_photo: Callable[[Photo, int, int], None],
        on_done: Callable[[], None],
        on_cancel: Callable[[], None],
    ):
        self._files     = files
        self._saved     = saved
        self._stop      = stop_event
        self._after     = after_fn
        self._on_known  = on_known
        self._on_photo  = on_photo
        self._on_done   = on_done
        self._on_cancel = on_cancel

    def run(self) -> None:
        known, to_read = reconcile(self._saved, self._files)
        self._after(0, self._on_known, known)
        total = len(to_read)
        for done, path in enumerate(to_read, start=1):
            if self._stop.is_set():
                self._after(0, self._on_cancel)
                return
            self._after(0, self._on_photo, _read(path), done, total)
        self._after(0, self._on_done)
