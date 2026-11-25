import pytest

from conference.names import shorten_middle

WHATSAPP = "WhatsApp Image 2026-11-14 at 18.42.07 (1).jpeg"


def test_matches_the_design_example():
    assert shorten_middle(WHATSAPP) == "WhatsApp Image 2026-11-1…(1).jpeg"


def test_result_fits_the_limit():
    for limit in (20, 25, 33, 40):
        assert len(shorten_middle(WHATSAPP, limit)) == limit


@pytest.mark.parametrize("name", ["4406833.jpg", "a" * 33, ""])
def test_a_name_that_fits_is_unchanged(name):
    assert shorten_middle(name) == name


def test_keeps_a_long_extension_whole():
    name = "Captura de tela 2026-11-14 191530 versão final.jpeg"
    result = shorten_middle(name, 30)
    assert result.endswith(".jpeg") and result.startswith("Captura de tela")
    assert "…" in result and len(result) == 30


def test_a_name_without_extension_keeps_its_end():
    result = shorten_middle("x" * 20 + "THE-END", 20)
    assert result.endswith("THE-END") and len(result) == 20


def test_a_tiny_limit_still_shows_the_start_and_the_end():
    result = shorten_middle(WHATSAPP, 12)
    assert result[0] == "W" and result.endswith(".jpeg") and len(result) == 12
