"""Photo quality measures used to pick between two shots of the same stub."""

import cv2
import numpy as np

# The width WhatsApp sends photos at. The Laplacian variance changes with the image size, so two shots are
# only comparable when measured at the same width.
COMPARABLE_WIDTH = 1600


def _gray(img: np.ndarray) -> np.ndarray:
    return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img


def sharpness(img: np.ndarray) -> float:
    """Variance of the Laplacian: higher means sharper edges."""
    return float(cv2.Laplacian(_gray(img), cv2.CV_64F).var())


def comparable_sharpness(img: np.ndarray) -> float:
    """Sharpness of the whole photo resized to COMPARABLE_WIDTH, so a photo read by QR and its duplicate read
    by OCR are measured the same way (#38)."""
    gray = _gray(img)
    height, width = gray.shape
    size = (COMPARABLE_WIDTH, round(height * COMPARABLE_WIDTH / width))
    return sharpness(cv2.resize(gray, size, interpolation=cv2.INTER_AREA))
