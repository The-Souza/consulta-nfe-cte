"""Checks the pipeline against real stub photos kept only on the developer's machine.

The photos and their expected invoice numbers (`esperado.csv`: `arquivo,nfe`) hold third-party data,
so they live in `docs/imgs-test/`, outside git. Without that folder (as in CI) the module is skipped.
Run only the fast tests with `pytest -m "not slow"`.
"""

import csv
import time
from pathlib import Path

import cv2
import numpy as np
import pytest

from image_pipeline import pipeline
from image_pipeline.date_area import date_area
from image_pipeline.pipeline import process, process_batch

PHOTOS = Path(__file__).resolve().parents[2] / "docs" / "imgs-test"
EXPECTED = PHOTOS / "esperado.csv"

pytestmark = [
    pytest.mark.slow,
    pytest.mark.skipif(not EXPECTED.exists(), reason="local real photos not available"),
]

TURNS = {90: cv2.ROTATE_90_CLOCKWISE, 180: cv2.ROTATE_180, 270: cv2.ROTATE_90_COUNTERCLOCKWISE}
MIN_QR_SHARE = 2 / 3
SECONDS_PER_PHOTO = 60 / 50  # R15: 50 photos in a minute


@pytest.fixture(scope="module")
def expected() -> dict[Path, int]:
    with EXPECTED.open(encoding="utf-8") as file:
        return {PHOTOS / row["arquivo"]: int(row["nfe"]) for row in csv.DictReader(file)}


def turned_copies(expected: dict[Path, int], degrees: int, folder: Path) -> dict[Path, int]:
    copies = {}
    for path, nfe in expected.items():
        img = cv2.imdecode(np.fromfile(str(path), np.uint8), cv2.IMREAD_COLOR)
        target = folder / path.name
        cv2.imencode(".jpg", cv2.rotate(img, TURNS[degrees]), [cv2.IMWRITE_JPEG_QUALITY, 95])[1].tofile(str(target))
        copies[target] = nfe
    return copies


@pytest.mark.parametrize("degrees", [0, 90, 180, 270])
def test_qr_reads_most_photos_without_errors_in_any_turn(expected, degrees, tmp_path):
    photos = expected if degrees == 0 else turned_copies(expected, degrees, tmp_path)
    results = [process(path) for path in photos]
    by_qr = [(r, photos[r.path]) for r in results if r.nfe_source == "qr"]
    assert len(by_qr) >= MIN_QR_SHARE * len(photos)
    assert all(r.nfe == nfe for r, nfe in by_qr), "an invoice read from the QR must never be wrong"
    assert all(r.rotation == degrees for r, _ in by_qr)
    assert all(r.error is None for r in results)


def test_ocr_is_tried_when_the_qr_fails(expected, monkeypatch):
    calls = []
    real_ocr = pipeline.ocr.process_image

    def spy(path: str):
        calls.append(path)
        return real_ocr(path)

    monkeypatch.setattr(pipeline.ocr, "process_image", spy)
    results = [process(path) for path in expected]
    without_qr = [r for r in results if r.nfe_source != "qr"]
    assert sorted(calls) == sorted(str(r.path) for r in without_qr)
    assert all(r.nfe_source == "ocr" for r in without_qr if r.nfe is not None)


def test_batch_meets_the_time_budget(expected):
    start = time.perf_counter()
    process_batch(list(expected))
    assert time.perf_counter() - start <= SECONDS_PER_PHOTO * len(expected)


def test_date_area_finds_a_label_in_most_photos(expected):
    areas = [r.receipt_area for r in map(process, expected) if r.receipt_area is not None]
    anchored = sum(date_area(area).anchored for area in areas)
    assert anchored >= MIN_QR_SHARE * len(areas)
