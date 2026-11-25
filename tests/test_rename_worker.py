import threading
from pathlib import Path

import cv2
import numpy as np
import pytest

from image_pipeline import CanhotoResult
from ui.workers import rename
from ui.workers.rename import RenameWorker

PHOTO = np.arange(40 * 60 * 3, dtype=np.uint8).reshape(40, 60, 3)


class Run:
    """Runs a RenameWorker synchronously and records its callbacks."""

    def __init__(self, folder: Path, stop: threading.Event | None = None):
        self.updates: list[tuple] = []
        self.done: list[str] = []
        self.cancelled = False
        self.stop = stop or threading.Event()
        RenameWorker(
            folder=str(folder),
            stop_event=self.stop,
            after_fn=lambda _delay, fn, *args: fn(*args),
            on_update=lambda *args: self.updates.append(args),
            on_done=self.done.append,
            on_cancel=self._cancel,
        ).run()

    def _cancel(self):
        self.cancelled = True

    @property
    def statuses(self) -> list[tuple[str, str | None, str]]:
        return [(filename, nfe, status) for filename, nfe, status, *_ in self.updates]


def write_photo(path: Path, img: np.ndarray = PHOTO) -> bytes:
    cv2.imencode(".jpg", img)[1].tofile(str(path))
    return path.read_bytes()


def decode(path: Path) -> np.ndarray:
    return cv2.imdecode(np.fromfile(str(path), np.uint8), cv2.IMREAD_COLOR)


@pytest.fixture
def results(monkeypatch):
    """Scripts what image_pipeline.process returns per file name; an Exception is raised."""
    by_name: dict = {}

    def fake_process(path):
        outcome = by_name[Path(path).name]
        if isinstance(outcome, Exception):
            raise outcome
        outcome.path = Path(path)
        return outcome

    monkeypatch.setattr(rename.image_pipeline, "process", fake_process)
    return by_name


def read(nfe=None, rotation=0, upright=None, **fields) -> CanhotoResult:
    return CanhotoResult(Path("x"), nfe=nfe, nfe_source="qr" if nfe else None, rotation=rotation,
                         upright=PHOTO if upright is None else upright, **fields)


class TestRenamed:
    def test_a_straight_photo_is_moved_byte_for_byte(self, tmp_path, results):
        original = write_photo(tmp_path / "a.jpg")
        results["a.jpg"] = read(nfe=4406833)
        run = Run(tmp_path)
        assert run.statuses == [("a.jpg", "4406833", "ok")]
        assert (tmp_path / "renomeadas" / "4406833.jpg").read_bytes() == original
        assert not (tmp_path / "a.jpg").exists()
        assert not (tmp_path / "renomeadas" / "originais").exists()

    def test_a_turned_photo_is_saved_upright_and_the_original_kept(self, tmp_path, results):
        turned = cv2.rotate(PHOTO, cv2.ROTATE_90_CLOCKWISE)
        original = write_photo(tmp_path / "a.jpg", turned)
        results["a.jpg"] = read(nfe=4406833, rotation=90, upright=PHOTO)
        run = Run(tmp_path)
        assert run.statuses == [("a.jpg", "4406833", "ok")]
        saved = decode(tmp_path / "renomeadas" / "4406833.jpg")
        assert saved.shape == PHOTO.shape
        assert (tmp_path / "renomeadas" / "originais" / "a.jpg").read_bytes() == original
        assert not (tmp_path / "a.jpg").exists()

    def test_an_original_with_the_same_name_is_not_overwritten(self, tmp_path, results):
        kept = tmp_path / "renomeadas" / "originais"
        kept.mkdir(parents=True)
        (kept / "a.jpg").write_bytes(b"older")
        write_photo(tmp_path / "a.jpg")
        results["a.jpg"] = read(nfe=4406833, rotation=180)
        Run(tmp_path)
        assert (kept / "a.jpg").read_bytes() == b"older"
        assert (kept / "a (2).jpg").exists()


class TestNotRenamed:
    @pytest.mark.parametrize(
        "outcome, status",
        [
            (read(), "nao_encontrada"),
            (read(error="O arquivo não é uma imagem.", upright=None), "erro"),
            (read(ocr_unavailable=True), "erro"),
            (RuntimeError("boom"), "erro"),
        ],
        ids=["not-read", "broken-file", "ocr-unavailable", "unexpected"],
    )
    def test_the_photo_stays_in_the_folder(self, tmp_path, results, outcome, status):
        original = write_photo(tmp_path / "a.jpg")
        results["a.jpg"] = outcome
        run = Run(tmp_path)
        assert run.statuses == [("a.jpg", None, status)]
        assert (tmp_path / "a.jpg").read_bytes() == original

    def test_an_existing_destination_is_a_duplicate(self, tmp_path, results):
        (tmp_path / "renomeadas").mkdir()
        (tmp_path / "renomeadas" / "4406833.jpg").write_bytes(b"first")
        write_photo(tmp_path / "a.jpg")
        results["a.jpg"] = read(nfe=4406833, rotation=90)
        run = Run(tmp_path)
        assert run.statuses == [("a.jpg", "4406833", "duplicata")]
        assert (tmp_path / "renomeadas" / "4406833.jpg").read_bytes() == b"first"
        assert (tmp_path / "a.jpg").exists()


class TestRun:
    def test_reports_progress_and_the_output_folder(self, tmp_path, results):
        for name, nfe in (("a.jpg", 1), ("b.png", 2)):
            write_photo(tmp_path / name)
            results[name] = read(nfe=nfe)
        (tmp_path / "notes.txt").write_text("not a photo")
        run = Run(tmp_path)
        assert [(u[0], u[4], u[5]) for u in run.updates] == [("a.jpg", 1, 2), ("b.png", 2, 2)]
        assert run.updates[-1][3] == 1.0
        assert run.done == [str(tmp_path / "renomeadas")]

    def test_stops_between_photos_when_cancelled(self, tmp_path, results):
        for name, nfe in (("a.jpg", 1), ("b.jpg", 2)):
            write_photo(tmp_path / name)
            results[name] = read(nfe=nfe)
        stop = threading.Event()
        stop.set()
        run = Run(tmp_path, stop)
        assert run.cancelled and run.updates == [] and run.done == []
        assert (tmp_path / "a.jpg").exists()
