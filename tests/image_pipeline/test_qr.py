import cv2
import numpy as np
import pytest

from image_pipeline import qr
from image_pipeline.qr import read_key
from tests.image_pipeline.fakes import PHOTO_H, PHOTO_W, make_key, make_photo, make_stub

KEY = make_key()


def center_x(read) -> float:
    return float(read.points[:, 0].mean())


class TestSyntheticStub:
    def test_reads_a_straight_stub(self):
        read = read_key(make_photo(make_stub(KEY)))
        assert read is not None
        assert read.key == KEY

    def test_reads_a_tilted_stub(self):
        read = read_key(make_photo(make_stub(KEY), angle=8))
        assert read is not None and read.key == KEY

    def test_reads_an_upside_down_stub_with_the_qr_on_the_left(self):
        read = read_key(make_photo(make_stub(KEY), upside_down=True))
        assert read is not None and read.key == KEY
        assert center_x(read) < PHOTO_W / 2

    def test_points_are_the_qr_corners_on_the_right(self):
        read = read_key(make_photo(make_stub(KEY)))
        assert read.points.shape == (4, 2)
        assert center_x(read) > PHOTO_W / 2
        assert abs(read.points[:, 1].mean() - PHOTO_H / 2) < 20

    def test_reads_a_small_stub_by_upscaling_with_points_in_original_scale(self):
        photo = make_photo(make_stub(KEY), width=600)
        read = read_key(photo)
        assert read is not None and read.key == KEY
        assert 0 <= read.points[:, 0].min() and read.points[:, 0].max() <= PHOTO_W
        assert center_x(read) > PHOTO_W / 2

    def test_accepts_a_grayscale_photo(self):
        gray = cv2.cvtColor(make_photo(make_stub(KEY)), cv2.COLOR_BGR2GRAY)
        assert read_key(gray).key == KEY


TURNS = {90: cv2.ROTATE_90_CLOCKWISE, 180: cv2.ROTATE_180, 270: cv2.ROTATE_90_COUNTERCLOCKWISE}


class TestRotation:
    def test_straight_photo_has_no_rotation(self):
        assert read_key(make_photo(make_stub(KEY))).rotation == 0

    def test_a_few_degrees_of_tilt_rounds_to_no_rotation(self):
        assert read_key(make_photo(make_stub(KEY), angle=8)).rotation == 0

    @pytest.mark.parametrize("degrees", [90, 180, 270])
    def test_detects_how_far_the_photo_is_turned_clockwise(self, degrees):
        photo = cv2.rotate(make_photo(make_stub(KEY), angle=5), TURNS[degrees])
        read = read_key(photo)
        assert read is not None and read.key == KEY
        assert read.rotation == degrees

    def test_without_points_there_is_no_rotation(self):
        assert qr.QrRead(KEY, None).rotation == 0


class TestRejected:
    def test_cte_key_is_not_accepted(self):
        assert read_key(make_photo(make_stub(make_key(model="57")))) is None

    def test_qr_with_other_text_is_not_accepted(self):
        stub = make_stub()
        stub[40:260, 1300:1520] = cv2.cvtColor(
            cv2.resize(cv2.QRCodeEncoder.create().encode("https://example.com"), (220, 220),
                       interpolation=cv2.INTER_NEAREST),
            cv2.COLOR_GRAY2BGR,
        )
        assert read_key(make_photo(stub)) is None

    def test_photo_without_qr(self):
        assert read_key(make_photo(make_stub())) is None

    def test_blank_image(self):
        assert read_key(np.zeros((900, 1600, 3), np.uint8)) is None


class FakeDetector:
    """Decodes only the images accepted by `when`, returning fixed points in that image."""

    def __init__(self, when=lambda img: True, points=None, error=False):
        self.when, self.points, self.error, self.calls = when, points, error, []

    def detectAndDecode(self, img):  # noqa: N802 - OpenCV's name
        self.calls.append(img.shape)
        if self.error:
            raise cv2.error("decoder failure")
        if not self.when(img):
            return "", None, None
        return KEY, np.array([self.points], np.float32), None


class TestLadder:
    def test_detector_error_counts_as_not_read(self, monkeypatch):
        monkeypatch.setattr(qr, "_detectors", lambda: [FakeDetector(error=True)])
        assert read_key(np.zeros((100, 200), np.uint8)) is None

    def test_stops_at_the_first_valid_read(self, monkeypatch):
        detector = FakeDetector(points=[[0, 0], [10, 0], [10, 10], [0, 10]])
        monkeypatch.setattr(qr, "_detectors", lambda: [detector])
        read_key(np.zeros((100, 200), np.uint8))
        assert detector.calls == [(100, 200)]

    def test_upscaled_points_are_mapped_back(self, monkeypatch):
        detector = FakeDetector(when=lambda img: img.shape == (200, 400),
                                points=[[100, 40], [140, 40], [140, 80], [100, 80]])
        monkeypatch.setattr(qr, "_detectors", lambda: [detector])
        read = read_key(np.zeros((100, 200), np.uint8))
        assert read.points.tolist() == [[50, 20], [70, 20], [70, 40], [50, 40]]

    def test_half_crop_points_are_shifted_back(self, monkeypatch):
        right_half_2x = (200, 200)
        detector = FakeDetector(when=lambda img: img.shape == right_half_2x,
                                points=[[20, 40], [60, 40], [60, 80], [20, 80]])
        monkeypatch.setattr(qr, "_detectors", lambda: [detector])
        read = read_key(np.zeros((100, 200), np.uint8))
        assert read.points.tolist() == [[110, 20], [130, 20], [130, 40], [110, 40]]

    @pytest.mark.parametrize("text", ["", "not a key"])
    def test_text_without_a_valid_key_keeps_trying(self, monkeypatch, text):
        class Silent(FakeDetector):
            def detectAndDecode(self, img):  # noqa: N802
                self.calls.append(img.shape)
                return text, np.zeros((1, 4, 2), np.float32), None

        detector = Silent()
        monkeypatch.setattr(qr, "_detectors", lambda: [detector])
        assert read_key(np.zeros((100, 200), np.uint8)) is None
        assert len(detector.calls) > 1
