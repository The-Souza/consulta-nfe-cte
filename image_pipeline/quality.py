"""Photo quality measures used to pick between two shots of the same stub."""

import cv2
import numpy as np


def sharpness(img: np.ndarray) -> float:
    """Variance of the Laplacian: higher means sharper edges."""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())
