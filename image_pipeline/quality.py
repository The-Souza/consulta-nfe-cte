"""Photo quality measures used to pick between two shots of the same stub."""

import cv2
import numpy as np

# The longer side WhatsApp sends photos at. The Laplacian variance changes with the image size, so two shots
# are only comparable at the same size. The longer side is used, not the width: a photo left as it arrived
# may be standing or lying down, and fixing the width would enlarge (and soften) the standing one.
COMPARABLE_SIDE = 1600


def _gray(img: np.ndarray) -> np.ndarray:
    return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img


def sharpness(img: np.ndarray) -> float:
    """Variance of the Laplacian: higher means sharper edges."""
    return float(cv2.Laplacian(_gray(img), cv2.CV_64F).var())


def comparable_sharpness(img: np.ndarray) -> float:
    """Sharpness of the whole photo with its longer side resized to COMPARABLE_SIDE, so a photo read by QR and
    its duplicate read by OCR are measured the same way (#38)."""
    gray = _gray(img)
    height, width = gray.shape
    scale = COMPARABLE_SIDE / max(height, width)
    size = (round(width * scale), round(height * scale))
    # INTER_AREA enlarges almost like nearest neighbour: its hard pixel blocks would read as sharp edges and
    # inflate a small copy. It is only right for shrinking.
    interpolation = cv2.INTER_AREA if scale < 1 else cv2.INTER_LINEAR
    return sharpness(cv2.resize(gray, size, interpolation=interpolation))
