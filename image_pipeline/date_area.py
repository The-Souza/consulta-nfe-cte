"""Locates the date box inside the receipt area from the labels printed on every stub.

"DATA DO RECEBIMENTO" sits at the start of the date box and "IDENTIFICAÇÃO E ASSINATURA DO RECEBEDOR"
right after its end. When no label is read, the whole receipt area is returned. Reading takes about
2 s per photo, so this runs outside the batch, only where the date box is shown.
"""

import logging
import unicodedata
from dataclasses import dataclass
from difflib import SequenceMatcher

import cv2
import numpy as np
import pytesseract

from config import TESSERACT_PATH

pytesseract.pytesseract.tesseract_cmd = TESSERACT_PATH

logger = logging.getLogger(__name__)

SCALES = (3, 4)
MIN_RATIO = 0.8
MIN_LETTERS = 3

# Pixel distances in the receipt area, measured on the local test photos.
START_MARGIN = 15  # before "DATA"
RECEBIMENTO_AFTER_START = 90
IDENTIFICACAO_AFTER_START = 300
END_MARGIN = 5  # before "IDENTIFICAÇÃO"
DEFAULT_WIDTH = 300
MIN_WIDTH = 60

DATA, RECEBIMENTO, IDENTIFICACAO = "DATA", "RECEBIMENTO", "IDENTIFICACAO"
_LABELS = (DATA, RECEBIMENTO, IDENTIFICACAO)


@dataclass(frozen=True)
class DateArea:
    image: np.ndarray
    anchored: bool  # False when no label was read and image is the whole receipt area
    # Columns of the date box in the receipt area, kept in the review progress so the slow label search
    # does not run again when the photo is reopened; None when not anchored.
    bounds: tuple[int, int] | None = None


def _normalize(word: str) -> str:
    ascii_only = unicodedata.normalize("NFKD", word).encode("ascii", "ignore").decode()
    return ascii_only.upper().strip(" .,:;")


def _label_of(word: str) -> str | None:
    text = _normalize(word)
    if len(text) < MIN_LETTERS:
        return None
    for label in _LABELS:
        if SequenceMatcher(None, text, label).ratio() >= MIN_RATIO:
            return label
    return None


def _passes(gray: np.ndarray):
    for scale in SCALES:
        big = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
        yield scale, big
        yield scale, cv2.adaptiveThreshold(big, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 41, 12)


def _find_labels(area: np.ndarray) -> dict[str, int]:
    gray = cv2.cvtColor(area, cv2.COLOR_BGR2GRAY) if area.ndim == 3 else area
    found: dict[str, int] = {}
    for scale, image in _passes(gray):
        data = pytesseract.image_to_data(image, config="--psm 11", output_type=pytesseract.Output.DICT)
        for word, left in zip(data["text"], data["left"]):
            label = _label_of(word)
            if label and label not in found:
                found[label] = round(left / scale)
        if DATA in found and IDENTIFICACAO in found:
            break
    return found


def _bounds(found: dict[str, int], width: int) -> tuple[int, int]:
    if DATA in found:
        start = found[DATA] - START_MARGIN
    elif RECEBIMENTO in found:
        start = found[RECEBIMENTO] - RECEBIMENTO_AFTER_START
    else:
        start = found[IDENTIFICACAO] - IDENTIFICACAO_AFTER_START
    end = start + DEFAULT_WIDTH
    if IDENTIFICACAO in found and found[IDENTIFICACAO] - END_MARGIN >= start + MIN_WIDTH:
        end = found[IDENTIFICACAO] - END_MARGIN
    return max(0, start), min(width, end)


def date_area(area: np.ndarray) -> DateArea:
    try:
        found = _find_labels(area)
    except (pytesseract.TesseractNotFoundError, pytesseract.TesseractError) as error:
        logger.warning("Date box not located, Tesseract unavailable: %s", error)
        return DateArea(area, anchored=False)
    if not found:
        return DateArea(area, anchored=False)
    start, end = _bounds(found, area.shape[1])
    if end - start < MIN_WIDTH:
        return DateArea(area, anchored=False)
    return DateArea(area[:, start:end], anchored=True, bounds=(start, end))
