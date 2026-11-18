"""Static checks on UI source files: colors must come from ui/theme.py."""

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
UI_DIR = ROOT / "ui"
THEME_FILE = "ui/theme.py"

HEX_LITERAL = re.compile(r"""["']#[0-9a-fA-F]{3,8}["']""")

# Files still using hardcoded colors; cleaned up by the status-badges PR, which removes this list.
LEGACY_HEX_FILES = {
    "ui/frames/search.py",
    "ui/frames/upload.py",
    "ui/widgets/dropdown.py",
    "ui/widgets/history.py",
    "ui/widgets/table.py",
}


def _ui_sources() -> list[str]:
    return sorted(path.relative_to(ROOT).as_posix() for path in UI_DIR.rglob("*.py"))


def _hex_literals(relative_path: str) -> list[str]:
    return HEX_LITERAL.findall((ROOT / relative_path).read_text(encoding="utf-8"))


@pytest.mark.parametrize(
    "relative_path",
    [p for p in _ui_sources() if p != THEME_FILE and p not in LEGACY_HEX_FILES],
)
def test_ui_source_has_no_hex_colors(relative_path):
    assert _hex_literals(relative_path) == []


@pytest.mark.parametrize("relative_path", sorted(LEGACY_HEX_FILES))
def test_legacy_list_only_has_files_with_hex_colors(relative_path):
    assert _hex_literals(relative_path), f"{relative_path} is clean; remove it from LEGACY_HEX_FILES"
