import logging
import threading
from pathlib import Path

import pytest

from conference.photo import Photo
from conference.progress import file_hash
from image_pipeline import CanhotoResult
from ui.workers import load
from ui.workers.load import LoadWorker


class Run:
    """Runs a LoadWorker synchronously and records its callbacks."""

    def __init__(self, files: list[Path], saved: dict[str, Photo] | None = None,
                 stop: threading.Event | None = None):
        self.known: list[list[Photo]] = []
        self.read: list[tuple[Photo, int, int]] = []
        self.done = 0
        self.ocr_unavailable: bool | None = None
        self.cancelled = 0
        self.stop = stop or threading.Event()
        LoadWorker(
            files=files,
            saved=saved or {},
            stop_event=self.stop,
            after_fn=lambda _delay, fn, *args: fn(*args),
            on_known=self.known.append,
            on_photo=lambda photo, done, total: self.read.append((photo, done, total)),
            on_done=self._done,
            on_cancel=self._cancel,
        ).run()

    def _done(self, ocr_unavailable: bool):
        self.done += 1
        self.ocr_unavailable = ocr_unavailable

    def _cancel(self, ocr_unavailable: bool):
        self.cancelled += 1
        self.ocr_unavailable = ocr_unavailable

    @property
    def photos(self) -> dict[str, Photo]:
        return {photo.name: photo for photo, _, _ in self.read}


def put(folder: Path, name: str, content: bytes = b"photo") -> Path:
    path = folder / name
    path.write_bytes(content)
    return path


@pytest.fixture
def results(monkeypatch):
    """Scripts what image_pipeline.process returns per file name; an Exception is raised.

    The names it was called with are kept in `calls`, in order.
    """
    by_name: dict = {}
    calls: list[str] = []

    def fake_process(path, use_ocr=True):
        name = Path(path).name
        calls.append(name)
        outcome = by_name.get(name, CanhotoResult(Path(path)))
        if callable(outcome) and not isinstance(outcome, CanhotoResult):
            outcome = outcome()
        if isinstance(outcome, Exception):
            raise outcome
        outcome.path = Path(path)
        return outcome

    monkeypatch.setattr(load.image_pipeline, "process", fake_process)
    by_name["calls"] = calls
    return by_name


def read(nfe=None, **fields) -> CanhotoResult:
    return CanhotoResult(Path("x"), nfe=nfe, nfe_source="qr" if nfe else None, **fields)


class TestReuse:
    def test_an_unchanged_photo_is_not_read_again(self, tmp_path, results):
        path = put(tmp_path, "a.jpg")
        saved = Photo("a.jpg", file_hash(path), nfe=123, nfe_source="typed", confirmed=True)
        run = Run([path], {"a.jpg": saved})
        assert results["calls"] == []
        assert run.known == [[saved]]
        assert run.read == []
        assert run.done == 1

    def test_the_known_photos_come_before_any_reading(self, tmp_path, results):
        old = put(tmp_path, "old.jpg")
        new = put(tmp_path, "new.jpg", b"new")
        order = []
        results["new.jpg"] = lambda: order.append("read") or read(456)
        saved = {"old.jpg": Photo("old.jpg", file_hash(old), nfe=123)}
        LoadWorker(
            files=[old, new], saved=saved, stop_event=threading.Event(),
            after_fn=lambda _delay, fn, *args: fn(*args),
            on_known=lambda photos: order.append("known"),
            on_photo=lambda *_: None, on_done=lambda _ocr_unavailable: None,
            on_cancel=lambda _ocr_unavailable: None,
        ).run()
        assert order == ["known", "read"]

    def test_with_nothing_saved_the_known_list_is_empty(self, tmp_path, results):
        run = Run([put(tmp_path, "a.jpg")])
        assert run.known == [[]]

    def test_a_changed_photo_is_read_again(self, tmp_path, results):
        path = put(tmp_path, "a.jpg", b"changed")
        results["a.jpg"] = read(999)
        run = Run([path], {"a.jpg": Photo("a.jpg", "old-hash", nfe=123, confirmed=True)})
        assert run.known == [[]]
        photo = run.photos["a.jpg"]
        assert photo.nfe == 999
        assert not photo.confirmed


class TestReading:
    def test_a_new_photo_keeps_what_the_pipeline_read(self, tmp_path, results):
        path = put(tmp_path, "a.jpg")
        results["a.jpg"] = read(4406833, rotation=90, sharpness=12.5)
        photo = Run([path]).photos["a.jpg"]
        assert photo == Photo("a.jpg", file_hash(path), nfe=4406833, nfe_source="qr", rotation=90,
                              sharpness=12.5)

    def test_a_number_read_by_ocr_keeps_its_source(self, tmp_path, results):
        results["a.jpg"] = CanhotoResult(Path("x"), nfe=55, nfe_source="ocr")
        assert Run([put(tmp_path, "a.jpg")]).photos["a.jpg"].nfe_source == "ocr"

    def test_the_photos_are_read_in_order_with_the_progress(self, tmp_path, results):
        files = [put(tmp_path, f"{n}.jpg", n.encode()) for n in "abc"]
        run = Run(files)
        assert results["calls"] == ["a.jpg", "b.jpg", "c.jpg"]
        assert [(photo.name, done, total) for photo, done, total in run.read] == [
            ("a.jpg", 1, 3), ("b.jpg", 2, 3), ("c.jpg", 3, 3)]
        assert run.done == 1
        assert run.cancelled == 0

    def test_the_total_counts_only_the_photos_to_read(self, tmp_path, results):
        old = put(tmp_path, "old.jpg")
        new = put(tmp_path, "new.jpg", b"new")
        run = Run([old, new], {"old.jpg": Photo("old.jpg", file_hash(old))})
        assert [(done, total) for _, done, total in run.read] == [(1, 1)]

    def test_nothing_to_read_still_finishes(self, tmp_path, results):
        run = Run([])
        assert run.known == [[]]
        assert run.read == []
        assert run.done == 1


class TestFailures:
    def test_a_photo_without_a_number_is_unread(self, tmp_path, results):
        path = put(tmp_path, "a.jpg")
        results["a.jpg"] = read(None, error="could not open")
        photo = Run([path]).photos["a.jpg"]
        assert photo.nfe is None
        assert photo.file_hash == file_hash(path)

    def test_a_photo_that_breaks_the_pipeline_is_unread_and_the_rest_is_read(self, tmp_path, results, caplog):
        files = [put(tmp_path, "a.jpg", b"a"), put(tmp_path, "b.jpg", b"b")]
        results["a.jpg"] = RuntimeError("boom")
        results["b.jpg"] = read(222)
        with caplog.at_level(logging.ERROR):
            run = Run(files)
        assert run.photos["a.jpg"] == Photo("a.jpg", file_hash(files[0]))
        assert run.photos["b.jpg"].nfe == 222
        assert run.done == 1
        assert "a.jpg" in caplog.text

    def test_a_photo_that_cannot_be_hashed_is_unread_and_read_again_next_time(self, tmp_path, results):
        gone = tmp_path / "gone.jpg"
        results["gone.jpg"] = RuntimeError("no such file")
        run = Run([gone])
        assert run.photos["gone.jpg"] == Photo("gone.jpg", "")
        assert run.done == 1


class TestOcrUnavailable:
    def test_a_load_with_ocr_working_says_so(self, tmp_path, results):
        results["a.jpg"] = read(None)
        assert Run([put(tmp_path, "a.jpg")]).ocr_unavailable is False

    def test_a_photo_whose_number_was_never_tried_is_unread_and_reported(self, tmp_path, results):
        files = [put(tmp_path, "a.jpg", b"a"), put(tmp_path, "b.jpg", b"b")]
        results["a.jpg"] = read(None, ocr_unavailable=True)
        results["b.jpg"] = read(222)
        run = Run(files)
        assert run.photos["a.jpg"].nfe is None
        assert run.ocr_unavailable is True

    def test_a_cancelled_load_still_reports_it(self, tmp_path, results):
        stop = threading.Event()
        files = [put(tmp_path, "a.jpg", b"a"), put(tmp_path, "b.jpg", b"b")]
        results["a.jpg"] = lambda: stop.set() or read(None, ocr_unavailable=True)
        run = Run(files, stop=stop)
        assert run.cancelled == 1
        assert run.ocr_unavailable is True

    def test_a_load_cancelled_before_reading_has_nothing_to_report(self, tmp_path, results):
        stop = threading.Event()
        stop.set()
        assert Run([put(tmp_path, "a.jpg")], stop=stop).ocr_unavailable is False

    def test_nothing_read_means_nothing_to_report(self, tmp_path, results):
        path = put(tmp_path, "a.jpg")
        assert Run([path], {"a.jpg": Photo("a.jpg", file_hash(path))}).ocr_unavailable is False


class TestCancel:
    def test_cancelled_before_starting_reads_nothing(self, tmp_path, results):
        stop = threading.Event()
        stop.set()
        run = Run([put(tmp_path, "a.jpg")], stop=stop)
        assert results["calls"] == []
        assert run.read == []
        assert (run.done, run.cancelled) == (0, 1)

    def test_cancelled_midway_stops_after_the_current_photo(self, tmp_path, results):
        stop = threading.Event()
        files = [put(tmp_path, f"{n}.jpg", n.encode()) for n in "abc"]
        results["a.jpg"] = lambda: stop.set() or read(111)
        run = Run(files, stop=stop)
        assert results["calls"] == ["a.jpg"]
        assert [photo.name for photo, _, _ in run.read] == ["a.jpg"]
        assert (run.done, run.cancelled) == (0, 1)
