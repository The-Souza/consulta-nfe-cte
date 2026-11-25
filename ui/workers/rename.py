import logging
import os
import shutil
import time
from pathlib import Path
from typing import Callable

import cv2
import numpy as np

import image_pipeline
from utils.files import free_path

logger = logging.getLogger(__name__)

_IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png")
_JPEG_QUALITY = 95


def _write_file(data: np.ndarray, path: Path) -> None:
    # tofile: cv2.imwrite fails on Windows paths with accents.
    data.tofile(str(path))


def _save_upright(result: image_pipeline.CanhotoResult, target: Path, originals: Path) -> None:
    """Writes the photo turned back into position and moves the photo as it arrived to `originals`.

    Either both happen or neither: the image goes to a `.part` file (never listed by the upload step,
    which reads image extensions only) and becomes `target` only after the original is moved. A cut-off
    `target` would be uploaded, and the portal does not accept a second image for the same stub.
    """
    ok, data = cv2.imencode(".jpg", result.upright, [cv2.IMWRITE_JPEG_QUALITY, _JPEG_QUALITY])
    if not ok:
        raise OSError(f"could not encode {result.path.name}")
    partial = target.with_name(target.name + ".part")
    kept = free_path(originals / result.path.name)
    try:
        _write_file(data, partial)
        originals.mkdir(exist_ok=True)
        shutil.move(str(result.path), str(kept))
        os.replace(partial, target)
    except BaseException:
        partial.unlink(missing_ok=True)
        if kept.exists() and not result.path.exists():
            shutil.move(str(kept), str(result.path))
        raise


class RenameWorker:
    def __init__(
        self,
        folder: str,
        stop_event,
        after_fn: Callable,
        on_update: Callable,
        on_done: Callable,
        on_cancel: Callable,
    ):
        self._folder     = folder
        self._stop       = stop_event
        self._after      = after_fn
        self._on_update  = on_update
        self._on_done    = on_done
        self._on_cancel  = on_cancel

    def run(self) -> None:
        folder = self._folder
        output = Path(folder) / "renomeadas"
        output.mkdir(exist_ok=True)
        originals = output / "originais"

        files = sorted(f for f in os.listdir(folder) if f.lower().endswith(_IMAGE_EXTENSIONS))
        total = len(files)
        t0 = time.time()

        for i, filename in enumerate(files):
            if self._stop.is_set():
                self._after(0, self._on_cancel)
                return

            invoice_num = None
            try:
                invoice_num, status = self._rename(Path(folder) / filename, output, originals)
            except Exception:
                logger.exception("Could not rename %s", filename)
                status = "erro"

            prog    = (i + 1) / total
            elapsed = time.time() - t0
            self._after(0, self._on_update, filename, invoice_num, status, prog, i + 1, total, elapsed)

        self._after(0, self._on_done, str(output))

    @staticmethod
    def _rename(path: Path, output: Path, originals: Path) -> tuple[str | None, str]:
        result = image_pipeline.process(path)
        # Without Tesseract the number was never tried, so it is an error, not "not found".
        if result.error or result.ocr_unavailable:
            return None, "erro"
        if result.nfe is None:
            return None, "nao_encontrada"
        invoice_num = str(result.nfe)
        target = output / f"{invoice_num}.jpg"
        if target.exists():
            return invoice_num, "duplicata"
        if result.rotation == 0 and not result.exif_oriented:
            shutil.move(str(path), str(target))
        else:
            _save_upright(result, target, originals)
        return invoice_num, "ok"
