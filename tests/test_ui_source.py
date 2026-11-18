"""Static checks on UI source files: colors come from ui/theme.py and statuses carry no emoji."""

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
UI_DIR = ROOT / "ui"
THEME_FILE = "ui/theme.py"

HEX_LITERAL = re.compile(r"""["']#[0-9a-fA-F]{3,8}["']""")
# A color option given as a string literal ("gray", "white"...) instead of a theme token.
NAMED_COLOR = re.compile(r"""\b(?:\w*_color|bg|fg)\s*=\s*["'](?!transparent["'])[^"']*["']""")
EMOJI = re.compile(
    "[\U0001F300-\U0001FAFF☀-➿⬀-⯿⏩-⏺▶◀️]"
)


def _ui_sources() -> list[str]:
    return sorted(path.relative_to(ROOT).as_posix() for path in UI_DIR.rglob("*.py"))


def _read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


_NON_THEME_SOURCES = [p for p in _ui_sources() if p != THEME_FILE]


@pytest.mark.parametrize("relative_path", _NON_THEME_SOURCES)
def test_ui_source_has_no_hex_colors(relative_path):
    assert HEX_LITERAL.findall(_read(relative_path)) == []


@pytest.mark.parametrize("relative_path", _NON_THEME_SOURCES)
def test_ui_source_has_no_named_colors(relative_path):
    assert NAMED_COLOR.findall(_read(relative_path)) == []


@pytest.mark.parametrize("relative_path", [*_ui_sources(), "api.py"])
def test_source_has_no_emoji(relative_path):
    assert EMOJI.findall(_read(relative_path)) == []


# The patterns themselves -------------------------------------------------------

@pytest.mark.parametrize(
    "line", ['border_color="gray"', "hover_color='#444'", 'popup.configure(bg="white")', 'fg_color = "black"'],
)
def test_named_color_pattern_flags_literal_colors(line):
    assert NAMED_COLOR.search(line)


@pytest.mark.parametrize("line", ['fg_color="transparent"', "fg_color=theme.SURFACE", 'text="gray"'])
def test_named_color_pattern_allows_tokens_and_transparent(line):
    assert not NAMED_COLOR.search(line)


@pytest.mark.parametrize("text", ["✅ OK", "⚠ Sem CT-e", "❌ Erro", "⏹ Cancelar", "☑ Com imagem", "▶ Histórico", "⚠️"])
def test_emoji_pattern_flags_status_symbols(text):
    assert EMOJI.search(text)


@pytest.mark.parametrize("text", ["NF-e 1 → 9", "▾", "·", "—", "Não cadastrada", "Nº"])
def test_emoji_pattern_allows_plain_symbols(text):
    assert not EMOJI.search(text)
