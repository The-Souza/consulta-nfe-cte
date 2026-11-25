import pytest

from conference.folders import WorkFolder


@pytest.fixture
def work(tmp_path) -> WorkFolder:
    folder = WorkFolder(tmp_path / "Canhotos")
    folder.ensure()
    return folder


def put(folder, name: str, content: bytes = b"photo"):
    path = folder / name
    path.write_bytes(content)
    return path


class TestEnsure:
    def test_creates_the_input_and_discarded_folders(self, tmp_path):
        work = WorkFolder(tmp_path / "Canhotos")
        work.ensure()
        assert work.inputs_dir == tmp_path / "Canhotos" / "entrada" and work.inputs_dir.is_dir()
        assert work.discarded_dir == tmp_path / "Canhotos" / "descartadas" and work.discarded_dir.is_dir()

    def test_running_again_keeps_what_is_there(self, work):
        put(work.inputs_dir, "a.jpg")
        work.ensure()
        assert (work.inputs_dir / "a.jpg").exists()


class TestInputs:
    def test_lists_photos_in_name_order_ignoring_case(self, work):
        for name in ("b.jpeg", "C.PNG", "a.JPG"):
            put(work.inputs_dir, name)
        assert [p.name for p in work.inputs()] == ["a.JPG", "b.jpeg", "C.PNG"]

    def test_skips_other_files_and_subfolders(self, work):
        put(work.inputs_dir, "a.jpg")
        put(work.inputs_dir, ".conferencia.json", b"{}")
        put(work.inputs_dir, "notes.txt")
        (work.inputs_dir / "old.jpg").mkdir()
        (work.inputs_dir / "renomeadas").mkdir()
        put(work.inputs_dir / "renomeadas", "1.jpg")
        assert [p.name for p in work.inputs()] == ["a.jpg"]

    def test_a_missing_input_folder_has_no_photos(self, tmp_path):
        assert WorkFolder(tmp_path / "missing").inputs() == []


class TestCopyIn:
    def test_copies_and_keeps_the_original(self, work, tmp_path):
        source = put(tmp_path, "WhatsApp Image.jpeg", b"original")
        copied = work.copy_in([source])
        assert copied == [work.inputs_dir / "WhatsApp Image.jpeg"]
        assert copied[0].read_bytes() == b"original" and source.read_bytes() == b"original"

    def test_never_overwrites_a_photo_with_the_same_name(self, work, tmp_path):
        put(work.inputs_dir, "a.jpg", b"already here")
        copied = work.copy_in([put(tmp_path, "a.jpg", b"new")])
        assert copied == [work.inputs_dir / "a (2).jpg"]
        assert (work.inputs_dir / "a.jpg").read_bytes() == b"already here"

    def test_a_photo_already_in_the_input_folder_is_not_copied_again(self, work):
        inside = put(work.inputs_dir, "a.jpg")
        assert work.copy_in([inside]) == []
        assert [p.name for p in work.inputs()] == ["a.jpg"]

    def test_copies_several_in_order(self, work, tmp_path):
        sources = [put(tmp_path, name) for name in ("b.jpg", "a.jpg")]
        assert [p.name for p in work.copy_in(sources)] == ["b.jpg", "a.jpg"]


class TestDiscard:
    def test_moves_the_photo_to_the_discarded_folder(self, work):
        put(work.inputs_dir, "a.jpg", b"blurry")
        moved = work.discard("a.jpg")
        assert moved == work.discarded_dir / "a.jpg" and moved.read_bytes() == b"blurry"
        assert not (work.inputs_dir / "a.jpg").exists()

    def test_never_overwrites_a_discarded_photo(self, work):
        put(work.discarded_dir, "a.jpg", b"older")
        put(work.inputs_dir, "a.jpg", b"newer")
        assert work.discard("a.jpg") == work.discarded_dir / "a (2).jpg"
        assert (work.discarded_dir / "a.jpg").read_bytes() == b"older"

    def test_a_missing_photo_raises(self, work):
        with pytest.raises(FileNotFoundError):
            work.discard("gone.jpg")
