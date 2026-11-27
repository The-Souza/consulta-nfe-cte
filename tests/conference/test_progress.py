import ctypes
import json
import sys
from datetime import date, datetime

import pytest

from conference import progress
from conference.photo import Photo, SystemInfo
from conference.progress import FILE_NAME, file_hash, load, reconcile, save

CHECKED = datetime(2026, 11, 25, 9, 30)


def full_photo(name="a.jpg") -> Photo:
    return Photo(
        name=name, file_hash="abc123", nfe=4406833, nfe_source="typed", rotation=90,
        typed_date=date(2026, 11, 14), confirmed=True,
        system=SystemInfo("found", date(2026, 11, 13), CHECKED, "PENDENTE"),
        date_box=(120, 410), sharpness=812.5,
    )


def put(folder, name: str, content: bytes):
    path = folder / name
    path.write_bytes(content)
    return path


class TestRoundTrip:
    def test_every_field_comes_back(self, tmp_path):
        save(tmp_path, [full_photo()])
        assert load(tmp_path) == {"a.jpg": full_photo()}

    def test_a_photo_with_nothing_read_comes_back(self, tmp_path):
        bare = Photo(name="b.jpg", file_hash="h")
        save(tmp_path, [bare])
        assert load(tmp_path) == {"b.jpg": bare}

    def test_discarded_photos_are_not_kept(self, tmp_path):
        """They left entrada/, so there is nothing to resume for them."""
        gone = Photo(name="c.jpg", file_hash="h", discarded=True)
        save(tmp_path, [full_photo(), gone])
        assert list(load(tmp_path)) == ["a.jpg"]

    def test_saving_again_replaces_the_previous_progress(self, tmp_path):
        save(tmp_path, [full_photo("a.jpg")])
        save(tmp_path, [full_photo("b.jpg")])
        assert list(load(tmp_path)) == ["b.jpg"]

    def test_the_file_is_versioned_json(self, tmp_path):
        save(tmp_path, [full_photo()])
        data = json.loads((tmp_path / FILE_NAME).read_text(encoding="utf-8"))
        assert data["version"] == progress.VERSION and "a.jpg" in data["photos"]


@pytest.mark.skipif(sys.platform != "win32", reason="hidden attribute is a Windows feature")
class TestHidden:
    @staticmethod
    def hidden(path) -> bool:
        return bool(ctypes.windll.kernel32.GetFileAttributesW(str(path)) & 0x2)

    def test_the_file_is_hidden(self, tmp_path):
        save(tmp_path, [full_photo()])
        assert self.hidden(tmp_path / FILE_NAME)

    def test_it_stays_hidden_after_saving_again(self, tmp_path):
        """Replacing a hidden file drops the attribute, so it is set again on every save."""
        save(tmp_path, [full_photo()])
        save(tmp_path, [full_photo("b.jpg")])
        assert self.hidden(tmp_path / FILE_NAME) and list(load(tmp_path)) == ["b.jpg"]


class TestBrokenFile:
    def test_a_missing_file_is_empty(self, tmp_path):
        assert load(tmp_path) == {}

    @pytest.mark.parametrize(
        "content",
        ["{not json", "[]", '{"version": 99, "photos": {}}', '{"photos": {}}', '{"version": 1, "photos": []}'],
        ids=["corrupt", "not-an-object", "other-version", "no-version", "photos-not-an-object"],
    )
    def test_an_unusable_file_is_ignored_without_error(self, tmp_path, content, caplog):
        (tmp_path / FILE_NAME).write_text(content, encoding="utf-8")
        assert load(tmp_path) == {}
        assert FILE_NAME in caplog.text

    def test_a_broken_entry_is_skipped_and_the_rest_kept(self, tmp_path):
        save(tmp_path, [full_photo("a.jpg"), full_photo("b.jpg")])
        path = tmp_path / FILE_NAME
        data = json.loads(path.read_text(encoding="utf-8"))
        data["photos"]["a.jpg"]["typed_date"] = "not a date"
        # "r+" edits the existing file: Windows refuses to recreate a hidden file with "w".
        with path.open("r+", encoding="utf-8") as file:
            file.write(json.dumps(data))
            file.truncate()
        assert list(load(tmp_path)) == ["b.jpg"]

    def test_a_failed_save_keeps_the_previous_file_and_leaves_no_temporary(self, tmp_path, monkeypatch):
        save(tmp_path, [full_photo("a.jpg")])

        def held(_src, _dst):
            raise PermissionError("held by another program")

        monkeypatch.setattr(progress.os, "replace", held)
        with pytest.raises(PermissionError):
            save(tmp_path, [full_photo("b.jpg")])
        monkeypatch.undo()
        assert list(load(tmp_path)) == ["a.jpg"]
        assert sorted(p.name for p in tmp_path.iterdir()) == [FILE_NAME]

    def test_the_content_reaches_the_disk_before_the_swap(self, tmp_path, monkeypatch):
        calls = []
        real_fsync, real_replace = progress.os.fsync, progress.os.replace

        def fsync(fd):
            calls.append("fsync")
            real_fsync(fd)

        def replace(src, dst):
            calls.append("replace")
            real_replace(src, dst)

        monkeypatch.setattr(progress.os, "fsync", fsync)
        monkeypatch.setattr(progress.os, "replace", replace)
        save(tmp_path, [full_photo("a.jpg")])
        assert calls == ["fsync", "replace"]
        assert list(load(tmp_path)) == ["a.jpg"]


class TestReconcile:
    def test_an_unchanged_photo_is_reused(self, tmp_path):
        path = put(tmp_path, "a.jpg", b"photo")
        saved = {"a.jpg": Photo(name="a.jpg", file_hash=file_hash(path), nfe=1)}
        reuse, read = reconcile(saved, [path])
        assert reuse == [saved["a.jpg"]] and read == []

    def test_a_changed_photo_is_read_again(self, tmp_path):
        path = put(tmp_path, "a.jpg", b"new content")
        saved = {"a.jpg": Photo(name="a.jpg", file_hash="old hash", nfe=1)}
        assert reconcile(saved, [path]) == ([], [path])

    def test_a_new_photo_is_read(self, tmp_path):
        path = put(tmp_path, "b.jpg", b"photo")
        assert reconcile({}, [path]) == ([], [path])

    @pytest.fixture
    def held(self, tmp_path, monkeypatch):
        """A photo an antivirus or OneDrive holds while the review opens: hashing it fails."""
        path = put(tmp_path, "held.jpg", b"photo")
        real_hash = progress.file_hash

        def hash_or_fail(target):
            if target == path:
                raise PermissionError("held by another program")
            return real_hash(target)

        monkeypatch.setattr(progress, "file_hash", hash_or_fail)
        return path

    def test_a_saved_photo_that_cannot_be_checked_now_keeps_its_review(self, tmp_path, held, caplog):
        """Reading it again would throw away the typed number, date and confirmation; it is checked next time."""
        ok = put(tmp_path, "ok.jpg", b"other photo")
        saved = {
            "ok.jpg": Photo(name="ok.jpg", file_hash=file_hash(ok)),
            "held.jpg": Photo(name="held.jpg", file_hash="h", nfe=123, nfe_source="typed", confirmed=True),
        }
        reuse, read = reconcile(saved, [held, ok])
        assert [p.name for p in reuse] == ["held.jpg", "ok.jpg"] and read == []
        assert (reuse[0].nfe, reuse[0].nfe_source) == (123, "typed")
        assert "held.jpg" in caplog.text

    def test_a_photo_that_cannot_be_checked_now_must_be_confirmed_again(self, held):
        """It may be held because a new image is replacing it: it is never left ready to send unverified."""
        saved = {"held.jpg": Photo(name="held.jpg", file_hash="h", nfe=123, confirmed=True)}
        reuse, _ = reconcile(saved, [held])
        assert reuse[0].confirmed is False

    def test_a_photo_saved_without_hash_keeps_what_the_user_typed_and_gets_its_hash(self, tmp_path):
        """Its first hash failed (an antivirus scanning the new copy): a later load must not read it from
        scratch over the typed number and date."""
        path = put(tmp_path, "a.jpg", b"photo")
        saved = {"a.jpg": Photo(name="a.jpg", file_hash="", nfe=55, nfe_source="typed", typed_date=date(2026, 11, 20),
                                confirmed=True)}
        reuse, read = reconcile(saved, [path])
        assert read == [] and reuse[0].file_hash == file_hash(path)
        assert (reuse[0].nfe, reuse[0].typed_date, reuse[0].confirmed) == (55, date(2026, 11, 20), False)

    def test_a_photo_saved_without_hash_and_untouched_is_read_again(self, tmp_path):
        """Nothing typed to lose: reading it again gives its number another chance."""
        path = put(tmp_path, "a.jpg", b"photo")
        saved = {"a.jpg": Photo(name="a.jpg", file_hash="", nfe=None)}
        assert reconcile(saved, [path]) == ([], [path])

    def test_a_new_photo_that_cannot_be_checked_now_goes_to_reading(self, held):
        assert reconcile({}, [held]) == ([], [held])

    def test_a_photo_removed_after_the_listing_goes_to_reading(self, tmp_path):
        gone = tmp_path / "gone.jpg"
        assert reconcile({"gone.jpg": Photo(name="gone.jpg", file_hash="h")}, [gone]) == ([], [gone])

    def test_a_photo_that_left_the_folder_is_forgotten(self, tmp_path):
        path = put(tmp_path, "a.jpg", b"photo")
        saved = {
            "a.jpg": Photo(name="a.jpg", file_hash=file_hash(path)),
            "gone.jpg": Photo(name="gone.jpg", file_hash="h"),
        }
        reuse, read = reconcile(saved, [path])
        assert [p.name for p in reuse] == ["a.jpg"] and read == []


class TestFileHash:
    def test_same_content_same_hash(self, tmp_path):
        assert file_hash(put(tmp_path, "a.jpg", b"x" * 100_000)) == file_hash(put(tmp_path, "b.jpg", b"x" * 100_000))

    def test_different_content_different_hash(self, tmp_path):
        assert file_hash(put(tmp_path, "a.jpg", b"one")) != file_hash(put(tmp_path, "b.jpg", b"two"))
