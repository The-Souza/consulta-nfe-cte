import pytest

from ui.titlebar import hex_to_colorref


@pytest.mark.parametrize(
    ("color", "expected"),
    [
        ("#141416", 0x00161414),
        ("#1d7f55", 0x00557F1D),
        ("#FF0000", 0x000000FF),
        ("#0000ff", 0x00FF0000),
        ("#000000", 0),
    ],
)
def test_hex_to_colorref_swaps_to_bgr(color, expected):
    assert hex_to_colorref(color) == expected


@pytest.mark.parametrize("color", ["141416", "#fff", "#12345g", "", "#1414160"])
def test_hex_to_colorref_rejects_invalid(color):
    with pytest.raises(ValueError):
        hex_to_colorref(color)
