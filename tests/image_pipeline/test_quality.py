import cv2
import numpy as np

from image_pipeline.quality import sharpness


def checkerboard(size: int = 200, square: int = 10) -> np.ndarray:
    rows, cols = np.indices((size, size)) // square
    gray = ((rows + cols) % 2 * 255).astype(np.uint8)
    return cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)


def test_blurred_image_is_less_sharp():
    img = checkerboard()
    blurred = cv2.GaussianBlur(img, (0, 0), 3)
    assert sharpness(blurred) < sharpness(img)


def test_more_blur_means_less_sharp():
    img = checkerboard()
    light = cv2.GaussianBlur(img, (0, 0), 1)
    heavy = cv2.GaussianBlur(img, (0, 0), 4)
    assert sharpness(heavy) < sharpness(light)


def test_accepts_color_and_gray_with_the_same_result():
    img = checkerboard()
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    assert sharpness(img) == sharpness(gray)


def test_flat_image_has_zero_sharpness():
    assert sharpness(np.full((50, 50), 128, np.uint8)) == 0.0


def test_returns_a_float():
    assert isinstance(sharpness(checkerboard()), float)
