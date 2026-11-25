"""Turns stub photos into results: invoice number, upright photo, strip and hints."""

import logging
import threading
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import cv2
import numpy as np
import pytesseract
from PIL import Image

import ocr
from image_pipeline.access_key import nfe_from_key
from image_pipeline.filename_hint import FilenameHint, hint_from_filename
from image_pipeline.qr import QrRead, read_key
from image_pipeline.quality import comparable_sharpness
from image_pipeline.strip import receipt_area, straighten, upright

logger = logging.getLogger(__name__)

NfeSource = Literal["qr", "ocr"]
ProgressCallback = Callable[[int, int, "CanhotoResult"], None]

_EXIF_ORIENTATION = 0x0112
# The pixels as stored, without the EXIF orientation tag: the QR then measures how the pixels are turned,
# which is what matters for a viewer (or the portal) that ignores the tag.
_RAW_PIXELS = cv2.IMREAD_COLOR | cv2.IMREAD_IGNORE_ORIENTATION


@dataclass(eq=False)
class CanhotoResult:
    path: Path
    nfe: int | None = None
    nfe_source: NfeSource | None = None
    access_key: str | None = None
    rotation: int = 0  # how far the photo was turned clockwise, from the QR; 0 without QR
    upright: np.ndarray | None = None  # the whole photo in the right position; None if it did not open
    strip: np.ndarray | None = None  # straightened from the QR; None without QR
    receipt_area: np.ndarray | None = None  # date and signature; None without QR
    sharpness: float = 0.0  # of the upright photo with its longer side at COMPARABLE_SIDE, with or without QR
    hint: FilenameHint | None = None
    error: str | None = None  # why the photo could not be read
    ocr_unavailable: bool = False  # no QR and Tesseract missing or failing, so the number was not tried
    # The file carries an EXIF orientation tag (Windows Explorer rotates JPEGs that way), so moving it as
    # is would rely on the viewer honouring the tag: it must be rewritten from `upright`.
    exif_oriented: bool = False


def _open(path: Path, flags: int = _RAW_PIXELS) -> np.ndarray | None:
    # np.fromfile + imdecode: cv2.imread fails on Windows paths with accents.
    data = np.fromfile(str(path), dtype=np.uint8)
    if data.size == 0:  # imdecode raises on an empty buffer (a failed copy leaves 0-byte files)
        return None
    return cv2.imdecode(data, flags)


def _has_exif_orientation(path: Path) -> bool:
    # The tag is only a hint: any failure reading it (Pillow raises SyntaxError, struct.error and others on
    # a corrupt EXIF block) counts as no tag, so it never costs a photo whose QR was read.
    try:
        with Image.open(path) as image:
            return image.getexif().get(_EXIF_ORIENTATION, 1) != 1
    except Exception as error:
        logger.warning("Could not read the EXIF of %s: %s", path.name, error)
        return False


def _from_qr(result: CanhotoResult, img: np.ndarray, read: QrRead) -> None:
    result.nfe, result.nfe_source, result.access_key = nfe_from_key(read.key), "qr", read.key
    result.rotation = read.rotation
    result.upright = upright(img, read.rotation)
    if read.points is not None:
        stub = straighten(img, read.points)
        result.strip, result.receipt_area = stub.image, receipt_area(stub)


def _upright_without_qr(result: CanhotoResult, img: np.ndarray) -> None:
    # Without a QR the EXIF tag is the only hint of the right position, so apply it.
    result.upright = _open(result.path, cv2.IMREAD_COLOR) if result.exif_oriented else img


def _from_ocr(result: CanhotoResult) -> None:
    try:
        number = ocr.process_image(str(result.path))
    except (pytesseract.TesseractNotFoundError, pytesseract.TesseractError) as error:
        logger.warning("OCR unavailable for %s: %s", result.path.name, error)
        result.ocr_unavailable = True
        return
    if number:
        result.nfe, result.nfe_source = int(number), "ocr"


def process(path: str | Path, use_ocr: bool = True) -> CanhotoResult:
    """Reads one photo. Never raises: a photo that cannot be read comes back with `error` set.

    With `use_ocr=False` a photo without a readable QR is not read by OCR (the slow step): used to rebuild
    the crops of a photo whose invoice number is already known.
    """
    result = CanhotoResult(Path(path))
    result.hint = hint_from_filename(str(result.path))
    try:
        img = _open(result.path)
    except OSError as error:
        logger.warning("Could not open %s: %s", result.path.name, error)
        result.error = "Não foi possível abrir o arquivo."
        return result
    if img is None:
        result.error = "O arquivo não é uma imagem."
        return result
    try:
        result.exif_oriented = _has_exif_orientation(result.path)
        read = read_key(img)
        if read:
            _from_qr(result, img, read)
        else:
            _upright_without_qr(result, img)
            if use_ocr:
                _from_ocr(result)
        result.sharpness = comparable_sharpness(result.upright)
    except Exception:
        logger.exception("Unexpected failure reading %s", result.path.name)
        return CanhotoResult(result.path, hint=result.hint, error="Erro inesperado ao ler a foto.")
    return result


def process_batch(
    paths: Sequence[str | Path],
    stop_event: threading.Event | None = None,
    on_progress: ProgressCallback | None = None,
) -> list[CanhotoResult]:
    """Processes photos in order on the calling thread, checking for cancellation between photos."""
    results: list[CanhotoResult] = []
    for done, path in enumerate(paths, start=1):
        if stop_event is not None and stop_event.is_set():
            break
        result = process(path)
        results.append(result)
        if on_progress is not None:
            on_progress(done, len(paths), result)
    return results
