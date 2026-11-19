import re

from ui import theme

HEX_COLOR = re.compile(r"#[0-9a-fA-F]{6}")
NON_COLOR_STRINGS = {"FONT_FAMILY", "FONT_MONO"}
TRANSPARENT = "transparent"


def _color_constants() -> dict[str, str]:
    return {
        name: value
        for name, value in vars(theme).items()
        if name.isupper() and isinstance(value, str) and name not in NON_COLOR_STRINGS
    }


def test_color_constants_exist():
    assert _color_constants()


def test_color_constants_are_hex_or_transparent():
    invalid = {
        name: value
        for name, value in _color_constants().items()
        if value != TRANSPARENT and not HEX_COLOR.fullmatch(value)
    }
    assert invalid == {}


def test_status_has_all_tones():
    assert set(theme.STATUS) == {"ok", "warning", "error", "connection", "info", "neutral"}


def test_status_colors_are_hex_pairs():
    for tone, colors in theme.STATUS.items():
        assert len(colors) == 2, tone
        for color in colors:
            assert HEX_COLOR.fullmatch(color), (tone, color)


def test_banner_colors_cover_every_tone():
    assert set(theme.BANNER) == set(theme.STATUS)
    for tone, colors in theme.BANNER.items():
        assert len(colors) == 3, tone  # text, bottom line, button outline
        for color in colors:
            assert HEX_COLOR.fullmatch(color), (tone, color)


def test_radii_and_spacing_are_positive_ints():
    names = [n for n in vars(theme) if n.startswith(("RADIUS_", "SPACE_", "FONT_SIZE_"))]
    assert names
    for name in names:
        value = getattr(theme, name)
        assert isinstance(value, int) and value > 0, name
