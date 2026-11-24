import cv2
import numpy as np
import pytest

from image_pipeline import strip as strip_module
from image_pipeline.qr import read_key
from image_pipeline.strip import STRIP_H, STRIP_W, receipt_area, straighten, upright
from tests.image_pipeline.fakes import make_key, make_photo, make_stub

KEY = make_key()
TURNS = {90: cv2.ROTATE_90_CLOCKWISE, 180: cv2.ROTATE_180, 270: cv2.ROTATE_90_COUNTERCLOCKWISE}
STUB_LEFT_BORDER_X = 20  # where make_stub draws the frame's left line


def stub_left_units() -> float:
    """The synthetic frame's left line, in QR sides from the QR's left edge, as the detector sees the QR
    (the encoder adds a quiet zone, so the code is smaller than the pasted image)."""
    points = read_key(make_stub(KEY)).points
    qr_left = points[:, 0].min()
    side = points[:, 0].max() - qr_left
    return (STUB_LEFT_BORDER_X - qr_left) / side


def strip_of(photo: np.ndarray) -> np.ndarray:
    read = read_key(photo)
    assert read is not None, "the synthetic QR should be readable"
    return straighten(photo, read.points)


def in_perspective(photo: np.ndarray) -> np.ndarray:
    h, w = photo.shape[:2]
    src = np.float32([[0, 0], [w, 0], [w, h], [0, h]])
    dst = np.float32([[60, 30], [w - 20, 0], [w, h], [0, h - 50]])
    return cv2.warpPerspective(photo, cv2.getPerspectiveTransform(src, dst), (w, h), borderValue=(90, 90, 90))


class TestUpright:
    @pytest.mark.parametrize("degrees", [90, 180, 270])
    def test_undoes_each_turn_exactly(self, degrees):
        img = np.arange(6 * 4 * 3, dtype=np.uint8).reshape(6, 4, 3)
        assert np.array_equal(upright(cv2.rotate(img, TURNS[degrees]), degrees), img)

    def test_no_rotation_returns_the_same_image(self):
        img = np.zeros((6, 4, 3), np.uint8)
        assert upright(img, 0) is img

    def test_rejects_a_rotation_that_is_not_a_quarter_turn(self):
        with pytest.raises(ValueError):
            upright(np.zeros((6, 4, 3), np.uint8), 45)


class TestStraighten:
    @pytest.mark.parametrize(
        "make",
        [
            lambda: make_photo(make_stub(KEY)),
            lambda: make_photo(make_stub(KEY), angle=8),
            lambda: in_perspective(make_photo(make_stub(KEY))),
            lambda: cv2.rotate(make_photo(make_stub(KEY), angle=4), TURNS[90]),
            lambda: cv2.rotate(make_photo(make_stub(KEY)), TURNS[180]),
            lambda: cv2.rotate(make_photo(make_stub(KEY), angle=-4), TURNS[270]),
        ],
        ids=["straight", "tilted", "perspective", "turned-90", "turned-180", "turned-270"],
    )
    def test_puts_the_qr_upright_at_its_fixed_place(self, make):
        result = strip_of(make())
        assert result.shape == (STRIP_H, STRIP_W, 3)
        again = read_key(result)
        assert again is not None and again.key == KEY
        assert again.rotation == 0
        x0, y0 = strip_module.QR_LEFT, strip_module.QR_TOP
        size = strip_module.PX_PER_QR
        expected = np.float32([[x0, y0], [x0 + size, y0], [x0 + size, y0 + size], [x0, y0 + size]])
        assert np.abs(again.points - expected).max() < 8

    def test_the_stub_left_border_lands_left_of_the_receipt_area(self):
        result = cv2.cvtColor(strip_of(make_photo(make_stub(KEY))), cv2.COLOR_BGR2GRAY)
        border_x = round(strip_module.QR_LEFT + stub_left_units() * strip_module.PX_PER_QR)
        assert 0 < border_x < strip_module.QR_LEFT
        band = result[STRIP_H // 3: 2 * STRIP_H // 3, border_x - 6: border_x + 7]
        assert band.min() < 128

    def test_what_falls_outside_the_photo_is_white(self):
        photo = make_photo(make_stub(KEY))[:, 700:]  # the stub's left part is cut off
        result = strip_of(photo)
        assert result[:, :40].min() > 240

    def test_a_dark_photo_still_gives_a_readable_strip(self):
        dark = (make_photo(make_stub(KEY)) * 0.35).astype(np.uint8)
        result = strip_of(dark)
        assert read_key(result).key == KEY
        assert result.mean() > dark.mean()


class TestReceiptArea:
    def test_keeps_the_full_height_and_ends_before_the_qr(self):
        result = strip_of(make_photo(make_stub(KEY)))
        area = receipt_area(result)
        assert area.shape[0] == STRIP_H
        assert 0 < area.shape[1] < strip_module.QR_LEFT
        assert read_key(area) is None

    def test_starts_at_the_left_end_of_the_strip(self):
        result = strip_of(make_photo(make_stub(KEY)))
        assert np.array_equal(receipt_area(result)[:, :10], result[:, :10])
