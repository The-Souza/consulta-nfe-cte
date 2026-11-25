import struct
import threading
from pathlib import Path

import cv2
import numpy as np
import pytesseract
import pytest

import image_pipeline
from image_pipeline import pipeline
from image_pipeline.pipeline import CanhotoResult, process, process_batch
from image_pipeline.quality import comparable_sharpness
from image_pipeline.strip import STRIP_H, STRIP_W
from tests.image_pipeline.fakes import make_key, make_photo, make_stub, save_jpeg

NFE = 4406833
KEY = make_key(nfe=NFE)


def save(path: Path, img: np.ndarray) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    ok, data = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 95])
    assert ok
    data.tofile(str(path))
    return path


@pytest.fixture
def ocr_reads(monkeypatch):
    """Replaces the OCR fallback; returns the list of paths it was called with."""

    def install(result: str | None = None, error: Exception | None = None) -> list[str]:
        calls: list[str] = []

        def fake(path: str) -> str | None:
            calls.append(path)
            if error:
                raise error
            return result

        monkeypatch.setattr(pipeline.ocr, "process_image", fake)
        return calls

    return install


class TestQrPhoto:
    def test_reads_everything_from_the_qr(self, tmp_path, ocr_reads):
        calls = ocr_reads("1111111")
        photo = make_photo(make_stub(KEY))
        result = process(save(tmp_path / "foto.jpg", photo))
        assert result.error is None
        assert (result.nfe, result.nfe_source, result.access_key) == (NFE, "qr", KEY)
        assert result.rotation == 0
        assert result.upright.shape == photo.shape
        assert result.strip.shape == (STRIP_H, STRIP_W, 3)
        assert result.receipt_area is not None and result.receipt_area.shape[0] == STRIP_H
        assert result.sharpness > 0
        assert calls == []

    def test_a_turned_photo_comes_back_upright(self, tmp_path, ocr_reads):
        ocr_reads()
        photo = make_photo(make_stub(KEY))
        result = process(save(tmp_path / "foto.jpg", cv2.rotate(photo, cv2.ROTATE_90_CLOCKWISE)))
        assert result.rotation == 90
        assert result.upright.shape == photo.shape
        assert result.nfe == NFE

    def test_opens_a_path_with_accents_and_spaces(self, tmp_path, ocr_reads):
        ocr_reads()
        path = save(tmp_path / "canhotos ação" / "foto 1.jpg", make_photo(make_stub(KEY)))
        assert process(path).nfe == NFE

    def test_accepts_a_string_path(self, tmp_path, ocr_reads):
        ocr_reads()
        path = save(tmp_path / "foto.jpg", make_photo(make_stub(KEY)))
        result = process(str(path))
        assert result.path == path and result.nfe == NFE


class TestExifOrientation:
    """Windows Explorer rotates a JPEG by adding an EXIF orientation tag and leaving the pixels as they
    are. The rotation must come from the pixels, so the saved photo is upright in any viewer."""

    # EXIF 6 means "turn 90° clockwise to display": the pixels are the photo turned 90° counterclockwise.
    def stored_sideways(self, display: np.ndarray) -> np.ndarray:
        return cv2.rotate(display, cv2.ROTATE_90_COUNTERCLOCKWISE)

    def test_rotation_comes_from_the_pixels_not_the_tag(self, tmp_path, ocr_reads):
        ocr_reads()
        display = make_photo(make_stub(KEY))
        result = process(save_jpeg(tmp_path / "foto.jpg", self.stored_sideways(display), orientation=6))
        assert result.nfe == NFE
        assert result.rotation == 270
        assert result.upright.shape == display.shape
        assert result.exif_oriented

    def test_a_tag_on_upright_pixels_is_flagged(self, tmp_path, ocr_reads):
        ocr_reads()
        display = make_photo(make_stub(KEY))
        result = process(save_jpeg(tmp_path / "foto.jpg", display, orientation=6))
        assert result.rotation == 0
        assert result.upright.shape == display.shape
        assert result.exif_oriented

    def test_without_a_qr_the_tag_decides_the_position(self, tmp_path, ocr_reads):
        ocr_reads()
        display = make_photo(make_stub())
        result = process(save_jpeg(tmp_path / "foto.jpg", self.stored_sideways(display), orientation=6))
        assert result.rotation == 0
        assert result.upright.shape == display.shape
        assert result.exif_oriented

    @pytest.mark.parametrize("orientation", [None, 1])
    def test_no_tag_or_the_normal_tag_is_not_flagged(self, tmp_path, ocr_reads, orientation):
        ocr_reads()
        result = process(save_jpeg(tmp_path / "foto.jpg", make_photo(make_stub(KEY)), orientation))
        assert not result.exif_oriented

    @pytest.mark.parametrize("error", [SyntaxError("not a TIFF file"), struct.error("unpack requires a buffer")])
    def test_a_corrupt_exif_block_is_ignored(self, tmp_path, ocr_reads, monkeypatch, error):
        ocr_reads()

        class CorruptExif:
            def __enter__(self):
                return self

            def __exit__(self, *_):
                return False

            def getexif(self):
                raise error

        monkeypatch.setattr(pipeline.Image, "open", lambda _path: CorruptExif())
        result = process(save_jpeg(tmp_path / "foto.jpg", make_photo(make_stub(KEY))))
        assert (result.nfe, result.error, result.exif_oriented) == (NFE, None, False)

    def test_a_png_is_not_flagged(self, tmp_path, ocr_reads):
        ocr_reads()
        path = tmp_path / "foto.png"
        cv2.imencode(".png", make_photo(make_stub(KEY)))[1].tofile(str(path))
        assert not process(path).exif_oriented


class TestOcrFallback:
    def test_uses_the_ocr_when_there_is_no_qr(self, tmp_path, ocr_reads):
        calls = ocr_reads("4406833")
        photo = make_photo(make_stub())
        path = save(tmp_path / "foto.jpg", photo)
        result = process(path)
        assert calls == [str(path)]
        assert (result.nfe, result.nfe_source, result.access_key) == (NFE, "ocr", None)
        assert result.rotation == 0
        assert result.upright.shape == photo.shape
        assert result.strip is None and result.receipt_area is None
        assert result.sharpness > 0
        assert result.error is None

    def test_without_ocr_a_photo_without_qr_is_not_read(self, tmp_path, ocr_reads):
        calls = ocr_reads("4406833")
        result = process(save(tmp_path / "foto.jpg", make_photo(make_stub())), use_ocr=False)
        assert calls == []
        assert (result.nfe, result.nfe_source, result.ocr_unavailable, result.error) == (None, None, False, None)
        assert result.upright is not None

    def test_without_ocr_a_qr_photo_is_read_as_usual(self, tmp_path, ocr_reads):
        ocr_reads()
        result = process(save(tmp_path / "foto.jpg", make_photo(make_stub(KEY))), use_ocr=False)
        assert (result.nfe, result.nfe_source) == (NFE, "qr")
        assert result.strip is not None

    def test_nothing_read_leaves_the_invoice_empty(self, tmp_path, ocr_reads):
        ocr_reads(None)
        result = process(save(tmp_path / "foto.jpg", make_photo(make_stub())))
        assert (result.nfe, result.nfe_source, result.error) == (None, None, None)

    @pytest.mark.parametrize("error", [pytesseract.TesseractNotFoundError(), pytesseract.TesseractError(1, "x")])
    def test_tesseract_missing_or_failing_is_flagged_not_a_photo_error(self, tmp_path, ocr_reads, error):
        ocr_reads(error=error)
        result = process(save(tmp_path / "foto.jpg", make_photo(make_stub())))
        assert (result.nfe, result.error) == (None, None)
        assert result.ocr_unavailable

    def test_ocr_that_reads_nothing_is_not_flagged_unavailable(self, tmp_path, ocr_reads):
        ocr_reads(None)
        assert not process(save(tmp_path / "foto.jpg", make_photo(make_stub()))).ocr_unavailable

    def test_a_qr_read_never_flags_the_ocr(self, tmp_path, ocr_reads):
        ocr_reads(error=pytesseract.TesseractNotFoundError())
        assert not process(save(tmp_path / "foto.jpg", make_photo(make_stub(KEY)))).ocr_unavailable


class TestBrokenFiles:
    def test_a_text_file_is_reported_not_raised(self, tmp_path, ocr_reads):
        ocr_reads()
        path = tmp_path / "foto.jpg"
        path.write_text("not an image")
        result = process(path)
        assert result.error
        assert result.nfe is None and result.upright is None

    def test_an_empty_file_is_reported_not_raised(self, tmp_path, ocr_reads):
        ocr_reads()
        path = tmp_path / "foto.jpg"
        path.write_bytes(b"")
        result = process(path)
        assert result.error == "O arquivo não é uma imagem."
        assert result.nfe is None and result.upright is None

    def test_a_missing_file_is_reported_not_raised(self, tmp_path, ocr_reads):
        ocr_reads()
        result = process(tmp_path / "missing.jpg")
        assert result.error and result.nfe is None

    def test_an_unexpected_failure_is_reported_and_logged(self, tmp_path, ocr_reads, monkeypatch, caplog):
        ocr_reads()

        def boom(*_args):
            raise RuntimeError("boom")

        monkeypatch.setattr(pipeline, "straighten", boom)
        result = process(save(tmp_path / "foto.jpg", make_photo(make_stub(KEY))))
        assert result.error and result.nfe is None
        assert "boom" in caplog.text


@pytest.mark.parametrize("key", [KEY, None], ids=["with-qr", "without-qr"])
def test_sharpness_is_measured_the_same_way_with_or_without_qr(tmp_path, ocr_reads, key):
    """#38: a photo read by QR and its duplicate read by OCR must be comparable."""
    ocr_reads()
    result = process(save(tmp_path / "foto.jpg", make_photo(make_stub(key))))
    assert result.sharpness == comparable_sharpness(result.upright)


def test_reads_the_hint_from_the_file_name(tmp_path, ocr_reads):
    ocr_reads()
    path = save(tmp_path / "WhatsApp Image 2026-11-14 at 18.42.07.jpeg", make_photo(make_stub(KEY)))
    assert process(path).hint.label() == "Foto recebida no WhatsApp em 14/11 às 18:42"


class TestBatch:
    def photos(self, tmp_path) -> list[Path]:
        return [save(tmp_path / f"{n}.jpg", make_photo(make_stub(make_key(nfe=n)))) for n in (1, 2, 3)]

    def test_processes_in_order_and_reports_progress(self, tmp_path, ocr_reads):
        ocr_reads()
        progress = []
        results = process_batch(self.photos(tmp_path), on_progress=lambda d, t, r: progress.append((d, t, r.nfe)))
        assert [r.nfe for r in results] == [1, 2, 3]
        assert progress == [(1, 3, 1), (2, 3, 2), (3, 3, 3)]

    def test_stops_between_photos_when_cancelled(self, tmp_path, ocr_reads):
        ocr_reads()
        stop = threading.Event()
        results = process_batch(self.photos(tmp_path), stop_event=stop, on_progress=lambda *_: stop.set())
        assert len(results) == 1

    @pytest.mark.parametrize("content", [b"broken", b""], ids=["not-an-image", "empty"])
    def test_a_broken_photo_does_not_stop_the_batch(self, tmp_path, ocr_reads, content):
        ocr_reads()
        paths = self.photos(tmp_path)
        paths[1].write_bytes(content)
        results = process_batch(paths)
        assert [r.nfe for r in results] == [1, None, 3]
        assert results[1].error

    def test_empty_batch(self):
        assert process_batch([]) == []


def test_package_exports():
    assert image_pipeline.process is process
    assert image_pipeline.process_batch is process_batch
    assert image_pipeline.CanhotoResult is CanhotoResult
