import json
import os

import pytest

from sheet_sync.settings import Prefs, SyncConfig, load_config, load_prefs, save_prefs

SECRET = "sb_secret_test"


def _env(tmp_path, text):
    path = tmp_path / "enviar_planilha.env"
    path.write_text(text, encoding="utf-8")
    return path


# config -----------------------------------------------------------------------

def test_load_config_reads_the_three_values(tmp_path):
    path = _env(tmp_path, (
        "SUPABASE_URL=https://example.supabase.co/\n"
        f"SUPABASE_SECRET_KEY={SECRET}\n"
        "PLANILHA_PATH=C:\\Planilhas\\entregas.xlsx\n"
    ))

    config = load_config(path)

    assert config == SyncConfig("https://example.supabase.co", SECRET, "C:\\Planilhas\\entregas.xlsx")
    assert config.missing == []


def test_load_config_without_the_file_lists_what_is_missing(tmp_path):
    config = load_config(tmp_path / "enviar_planilha.env")

    assert config.missing == ["SUPABASE_URL", "SUPABASE_SECRET_KEY"]


def test_load_config_with_empty_values_lists_them_as_missing(tmp_path):
    config = load_config(_env(tmp_path, "SUPABASE_URL=https://example.supabase.co\nSUPABASE_SECRET_KEY=\n"))

    assert config.missing == ["SUPABASE_SECRET_KEY"]
    assert config.sheet_path == ""


def test_load_config_reads_a_file_saved_with_a_bom(tmp_path):
    # Windows tools like PowerShell 5 Set-Content save UTF-8 with a BOM before the first name
    path = tmp_path / "enviar_planilha.env"
    path.write_text(f"SUPABASE_URL=https://example.supabase.co\nSUPABASE_SECRET_KEY={SECRET}\n", encoding="utf-8-sig")

    assert load_config(path).missing == []


def test_load_config_does_not_touch_the_process_environment(tmp_path, monkeypatch):
    monkeypatch.delenv("SUPABASE_SECRET_KEY", raising=False)

    load_config(_env(tmp_path, f"SUPABASE_SECRET_KEY={SECRET}\n"))

    assert "SUPABASE_SECRET_KEY" not in os.environ


def test_config_repr_hides_the_secret_key():
    config = SyncConfig("https://example.supabase.co", SECRET, "")

    assert SECRET not in repr(config)
    assert SECRET not in str(config)


@pytest.mark.parametrize(("key", "expected"), [
    ("sb_publishable_abc", True),
    (SECRET, False),
    ("", False),
])
def test_config_detects_the_app_publishable_key(key, expected):
    assert SyncConfig("https://example.supabase.co", key, "").read_only_key is expected


# prefs ------------------------------------------------------------------------

def _prefs_file(tmp_path, content=None):
    path = tmp_path / "enviar_planilha.json"
    if content is not None:
        path.write_text(content, encoding="utf-8")
    return path


def test_load_prefs_without_a_file_returns_the_defaults(tmp_path):
    assert load_prefs(_prefs_file(tmp_path)) == Prefs()


@pytest.mark.parametrize("content", ["{not json", "[]", "null", '"text"'])
def test_load_prefs_with_an_unreadable_file_returns_the_defaults(tmp_path, content):
    assert load_prefs(_prefs_file(tmp_path, content)) == Prefs()


def test_load_prefs_ignores_values_of_the_wrong_type(tmp_path):
    path = _prefs_file(tmp_path, json.dumps({"path": 3, "columns": ["A"], "auto_send": "yes"}))

    assert load_prefs(path) == Prefs()


def test_save_and_load_prefs_round_trip(tmp_path):
    path = _prefs_file(tmp_path)
    prefs = Prefs(path="C:\\entregas.xlsx", columns={"nfe": "C", "cte": None, "driver": "A", "date": "B"},
                  auto_send=True)

    save_prefs(prefs, path)

    assert load_prefs(path) == prefs


def test_save_prefs_keeps_other_keys(tmp_path):
    path = _prefs_file(tmp_path, json.dumps({"other": 1, "path": "old.xlsx"}))

    save_prefs(Prefs(path="new.xlsx"), path)

    saved = json.loads(path.read_text(encoding="utf-8"))
    assert saved["other"] == 1
    assert saved["path"] == "new.xlsx"
