"""Turns the photo upright and straightens the stub strip, anchored on the QR code.

The paper edge is a poor anchor (white stub on white paper), and the date box sits at a different
distance from the QR on each stub. The QR corners, though, are found in every photo where the key is
read, so the strip is a fixed window around the QR, measured in QR sides.
"""

from dataclasses import dataclass

import cv2
import numpy as np

# Window in QR sides, from the QR's top-left corner. Measured on the local test photos: the printed
# frame starts 5.5 to 10.4 sides left of the QR and ends up to 4.0 sides right of it.
LEFT, RIGHT, TOP, BOTTOM = -11.5, 4.5, -0.4, 1.4
PX_PER_QR = 120

STRIP_W = round((RIGHT - LEFT) * PX_PER_QR)
STRIP_H = round((BOTTOM - TOP) * PX_PER_QR)
QR_LEFT = round(-LEFT * PX_PER_QR)
QR_TOP = round(-TOP * PX_PER_QR)
RECEIPT_MARGIN = round(0.1 * PX_PER_QR)

_UNDO_TURN = {
    90: cv2.ROTATE_90_COUNTERCLOCKWISE,
    180: cv2.ROTATE_180,
    270: cv2.ROTATE_90_CLOCKWISE,
}

_QR_TARGET = np.float32([
    [QR_LEFT, QR_TOP],
    [QR_LEFT + PX_PER_QR, QR_TOP],
    [QR_LEFT + PX_PER_QR, QR_TOP + PX_PER_QR],
    [QR_LEFT, QR_TOP + PX_PER_QR],
])

_WHITE = (255, 255, 255)


@dataclass(frozen=True)
class StubStrip:
    image: np.ndarray
    # First column where most pixels came from the photo; to its left the window fell outside the
    # photo and was filled with white.
    first_col: int


def upright(img: np.ndarray, rotation: int) -> np.ndarray:
    """Undoes a clockwise turn of 0, 90, 180 or 270 degrees, without resampling."""
    if rotation == 0:
        return img
    if rotation not in _UNDO_TURN:
        raise ValueError(f"rotation must be a quarter turn, got {rotation}")
    return cv2.rotate(img, _UNDO_TURN[rotation])


def _brighten(img: np.ndarray) -> np.ndarray:
    lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(4, 16))
    lab[:, :, 0] = clahe.apply(lab[:, :, 0])
    return cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)


def _first_photo_col(matrix: np.ndarray, photo_shape: tuple[int, ...]) -> int:
    inside = np.full(photo_shape[:2], 255, np.uint8)
    mask = cv2.warpPerspective(inside, matrix, (STRIP_W, STRIP_H), flags=cv2.INTER_NEAREST, borderValue=0)
    cols = np.flatnonzero((mask > 0).mean(axis=0) >= 0.5)
    return int(cols[0]) if cols.size else 0


def straighten(img: np.ndarray, qr_points: np.ndarray) -> StubStrip:
    """The stub strip, upright and flat, from the QR corners in the code's own order.

    Mapping the corners to fixed places undoes turn, tilt and perspective at once.
    """
    if img.ndim == 2:
        img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    matrix = cv2.getPerspectiveTransform(qr_points.astype(np.float32).reshape(4, 2), _QR_TARGET)
    image = cv2.warpPerspective(
        img, matrix, (STRIP_W, STRIP_H), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_CONSTANT, borderValue=_WHITE
    )
    return StubStrip(_brighten(image), _first_photo_col(matrix, img.shape))


def receipt_area(strip: StubStrip) -> np.ndarray:
    """Everything left of the QR that came from the photo: the delivery date and the signature."""
    end = QR_LEFT - RECEIPT_MARGIN
    return strip.image[:, min(strip.first_col, end - 1): end]
