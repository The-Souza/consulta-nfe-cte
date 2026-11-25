from utils.files import free_path


def test_a_free_name_is_kept(tmp_path):
    assert free_path(tmp_path / "a.jpg") == tmp_path / "a.jpg"


def test_a_taken_name_gets_a_counter(tmp_path):
    (tmp_path / "a.jpg").write_bytes(b"1")
    assert free_path(tmp_path / "a.jpg") == tmp_path / "a (2).jpg"


def test_the_counter_skips_taken_numbers(tmp_path):
    for name in ("a.jpg", "a (2).jpg", "a (3).jpg"):
        (tmp_path / name).write_bytes(b"1")
    assert free_path(tmp_path / "a.jpg") == tmp_path / "a (4).jpg"


def test_a_name_without_extension(tmp_path):
    (tmp_path / "nota").write_bytes(b"1")
    assert free_path(tmp_path / "nota") == tmp_path / "nota (2)"
