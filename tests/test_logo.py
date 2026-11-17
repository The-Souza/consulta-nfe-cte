from PIL import Image

from ui import icons


def _make_ico(path, color="red"):
    Image.new("RGBA", (64, 64), color).save(path, sizes=[(16, 16), (32, 32), (64, 64)])


def test_load_logo_from_ico_returns_rgba_at_requested_size(tmp_path):
    path = tmp_path / "icon.ico"
    _make_ico(path)

    logo = icons.load_logo(path, 88)

    assert logo is not None
    assert logo.mode == "RGBA"
    assert logo.size == (88, 88)
    assert logo.getpixel((44, 44)) == (255, 0, 0, 255)


def test_load_logo_missing_file_returns_none(tmp_path):
    assert icons.load_logo(tmp_path / "missing.ico", 88) is None


def test_load_logo_corrupt_file_returns_none(tmp_path):
    path = tmp_path / "icon.ico"
    path.write_bytes(b"not an icon")

    assert icons.load_logo(path, 88) is None
