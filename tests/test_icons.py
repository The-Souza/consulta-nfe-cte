import pytest
from PIL import Image

from ui import icons


def test_tint_applies_color_and_keeps_alpha():
    image = Image.new("RGBA", (2, 1))
    image.putpixel((0, 0), (255, 255, 255, 255))
    image.putpixel((1, 0), (255, 255, 255, 0))

    tinted = icons.tint(image, "#1d7f55")

    assert tinted.getpixel((0, 0)) == (0x1D, 0x7F, 0x55, 255)
    assert tinted.getpixel((1, 0))[3] == 0


def test_tint_keeps_partial_alpha():
    image = Image.new("RGBA", (1, 1), (255, 255, 255, 128))

    assert icons.tint(image, "#ffffff").getpixel((0, 0))[3] == 128


def test_get_icon_returns_cached_object():
    assert icons.get_icon("eye", 18) is icons.get_icon("eye", 18)


def test_get_icon_caches_per_color_and_size():
    base = icons.get_icon("eye", 18)

    assert icons.get_icon("eye", 18, "#5ee39a") is not base
    assert icons.get_icon("eye", 22) is not base


def test_get_icon_uses_requested_size():
    assert icons.get_icon("upload", 22).cget("size") == (22, 22)


def test_get_icon_missing_raises_with_name():
    with pytest.raises(FileNotFoundError, match="does-not-exist"):
        icons.get_icon("does-not-exist", 18)
