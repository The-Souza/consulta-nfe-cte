"""Reads the NF-e access key from the stub's QR code.

Tries a ladder of image variants, cheapest first, and stops at the first valid key. On the 15 local
test photos, the whole photo reads 10, upscaling adds 3 and the binarized half crop adds 1.
"""

import math
import threading
from collections.abc import Callable, Iterator
from dataclasses import dataclass

import cv2
import numpy as np

from image_pipeline.access_key import find_key

UPSCALE = 2


@dataclass(frozen=True)
class QrRead:
    key: str
    # 4×2 QR corners in the coordinates of the image given to read_key, in the code's own order:
    # top-left, top-right, bottom-right, bottom-left.
    points: np.ndarray | None

    @property
    def rotation(self) -> int:
        """How far the photo is turned clockwise (0, 90, 180 or 270), from the QR's top edge.

        The QR is printed upright on the stub, so its top edge points right in a straight photo.
        """
        if self.points is None:
            return 0
        (x0, y0), (x1, y1) = self.points[0], self.points[1]
        degrees = math.degrees(math.atan2(y1 - y0, x1 - x0))  # image y grows downwards
        return round(degrees / 90) % 4 * 90


@dataclass(frozen=True)
class _Variant:
    image: np.ndarray
    scale: float
    x_offset: int

    def to_original(self, points: np.ndarray) -> np.ndarray:
        mapped = points.reshape(-1, 2).astype(np.float32) / self.scale
        mapped[:, 0] += self.x_offset
        return mapped


_per_thread = threading.local()


def _detectors() -> list:
    """One pair per thread: OpenCV does not document the detectors as thread-safe, and the review screen reads
    QR codes from two workers at once."""
    detectors = getattr(_per_thread, "detectors", None)
    if detectors is None:
        detectors = _per_thread.detectors = [cv2.QRCodeDetector(), cv2.QRCodeDetectorAruco()]
    return detectors


def _upscale(gray: np.ndarray) -> np.ndarray:
    return cv2.resize(gray, None, fx=UPSCALE, fy=UPSCALE, interpolation=cv2.INTER_CUBIC)


def _otsu(gray: np.ndarray) -> np.ndarray:
    return cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]


def _sharpen(gray: np.ndarray) -> np.ndarray:
    return cv2.addWeighted(gray, 1.5, cv2.GaussianBlur(gray, (0, 0), 3), -0.5, 0)


def _variants(gray: np.ndarray) -> Iterator[_Variant]:
    yield _Variant(gray, 1, 0)
    yield _Variant(_upscale(gray), UPSCALE, 0)
    # The QR sits on the right of the stub, or on the left when the photo is upside down.
    half = gray.shape[1] // 2
    filters: list[Callable[[np.ndarray], np.ndarray]] = [_otsu, _sharpen]
    for x_offset, crop in ((half, gray[:, half:]), (0, gray[:, :half])):
        big = _upscale(crop)
        for apply in filters:
            yield _Variant(apply(big), UPSCALE, x_offset)


def _decode(detector, image: np.ndarray) -> tuple[str, np.ndarray | None]:
    try:
        text, points, _ = detector.detectAndDecode(image)
    except cv2.error:
        return "", None
    return text or "", points


def read_key(img: np.ndarray) -> QrRead | None:
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img
    for variant in _variants(gray):
        for detector in _detectors():
            text, points = _decode(detector, variant.image)
            key = find_key(text)
            if key:
                return QrRead(key, None if points is None else variant.to_original(points))
    return None
