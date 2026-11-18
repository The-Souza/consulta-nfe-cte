import pytest

from ui import theme
from utils import status
from utils.status import Tone


@pytest.mark.parametrize(
    ("label", "expected"),
    [
        (status.SEARCH_OK, Tone.OK),
        (status.SEARCH_NO_CTE, Tone.WARNING),
        (status.SEARCH_NOT_FOUND, Tone.ERROR),
    ],
)
def test_search_tone_for_known_labels(label, expected):
    assert status.search_tone(label) is expected


def test_search_labels_have_no_emoji():
    assert (status.SEARCH_OK, status.SEARCH_NO_CTE, status.SEARCH_NOT_FOUND) == ("OK", "Sem CT-e", "Não cadastrada")


@pytest.mark.parametrize("label", ["Tempo de conexão esgotado.", "Erro 500", "", "ok"])
def test_search_tone_for_any_other_text_is_error(label):
    assert status.search_tone(label) is Tone.ERROR


@pytest.mark.parametrize(
    ("key", "expected"),
    [
        ("ok", ("Renomeada", Tone.OK)),
        ("duplicata", ("Duplicata", Tone.WARNING)),
        ("nao_encontrada", ("Não lida", Tone.ERROR)),
        ("erro", ("Erro", Tone.ERROR)),
    ],
)
def test_rename_status_for_known_keys(key, expected):
    assert status.rename_status(key) == expected


def test_rename_status_for_unknown_key_is_error():
    assert status.rename_status("something-new") == ("Erro", Tone.ERROR)


def test_every_tone_has_theme_colors():
    assert {tone.value for tone in Tone} <= set(theme.STATUS)
