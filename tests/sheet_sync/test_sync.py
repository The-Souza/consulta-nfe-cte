import json
from datetime import date, datetime, timezone

import openpyxl
import responses

from sheet_sync.settings import SyncConfig
from sheet_sync.sheet import Columns, Ignored
from sheet_sync.sync import SyncResult, sync

SECRET = "sb_secret_test"
CONFIG = SyncConfig("https://example.supabase.co", SECRET, "")
TABLE = "https://example.supabase.co/rest/v1/entregas"
NOW = datetime(2026, 11, 22, 17, 20, tzinfo=timezone.utc)
COLUMNS = Columns(nfe="C", driver="A", date="B", cte="F")
HEADERS = ["Motorista", "Data", "NFe", "Cliente", "Destinatário", "CTe"]


def _sheet(tmp_path, rows):
    """Fictitious data only, laid out like the real sheet."""
    workbook = openpyxl.Workbook()
    workbook.active.append(HEADERS)
    for row in rows:
        workbook.active.append(row)
    path = tmp_path / "entregas.xlsx"
    workbook.save(path)
    return path


ROWS = [
    ["Ana", datetime(2026, 11, 22), 100, None, None, 25540],  # line 2: same as the table
    ["Bia", datetime(2026, 11, 22), 101, None, None, 25540],  # line 3: driver changed
    ["Caio", "21/11/2026", 102, None, None, None],            # line 4: new
    [None, None, 103, None, None, None],                      # line 5: ignored
]
STORED = [
    {"id": "a", "nfe": 100, "cte": 25540, "motorista": "Ana", "data_entrega": "2026-11-22"},
    {"id": "b", "nfe": 101, "cte": 25540, "motorista": "Davi", "data_entrega": "2026-11-22"},
]


def _posts():
    return [c for c in responses.calls if c.request.method == "POST"]


@responses.activate
def test_sync_sends_only_what_changed(tmp_path):
    responses.get(TABLE, json=STORED)
    responses.post(TABLE, status=201)
    responses.post(TABLE, status=200)

    result = sync(_sheet(tmp_path, ROWS), COLUMNS, CONFIG, now=NOW)

    assert result == SyncResult(finished_at=NOW, new=1, updated=1, unchanged=1, written=2,
                                ignored=[Ignored(5, "sem motorista")])
    inserted, merged = (json.loads(c.request.body) for c in _posts())
    assert inserted == [{"nfe": 102, "cte": None, "motorista": "Caio", "data_entrega": "2026-11-21",
                         "atualizado_em": NOW.isoformat()}]
    assert merged[0]["id"] == "b" and merged[0]["motorista"] == "Bia"


@responses.activate
def test_a_preview_counts_the_changes_without_writing(tmp_path):
    responses.get(TABLE, json=STORED)

    result = sync(_sheet(tmp_path, ROWS), COLUMNS, CONFIG, now=NOW, preview=True)

    assert result == SyncResult(finished_at=NOW, new=1, updated=1, unchanged=1, written=0,
                                ignored=[Ignored(5, "sem motorista")], preview=True)
    assert _posts() == []


@responses.activate
def test_sync_with_nothing_changed_reads_but_does_not_write(tmp_path):
    responses.get(TABLE, json=STORED[:1])

    result = sync(_sheet(tmp_path, ROWS[:1]), COLUMNS, CONFIG, now=NOW)

    assert (result.new, result.updated, result.unchanged, result.written, result.error) == (0, 0, 1, 0, None)
    assert _posts() == []


@responses.activate
def test_sync_with_a_missing_sheet_reports_it_without_any_request(tmp_path):
    result = sync(tmp_path / "sumiu.xlsx", COLUMNS, CONFIG, now=NOW)

    assert result.error == "Planilha não encontrada: sumiu.xlsx"
    assert len(responses.calls) == 0


@responses.activate
def test_sync_with_a_file_that_is_not_a_workbook(tmp_path):
    path = tmp_path / "texto.xlsx"
    path.write_text("não é planilha", encoding="utf-8")

    result = sync(path, COLUMNS, CONFIG, now=NOW)

    assert result.error == "O arquivo não é uma planilha .xlsx válida."
    assert len(responses.calls) == 0


@responses.activate
def test_sync_when_the_table_cant_be_read_keeps_the_ignored_rows(tmp_path):
    responses.get(TABLE, status=500)

    result = sync(_sheet(tmp_path, ROWS), COLUMNS, CONFIG, now=NOW)

    assert result.error == "O Supabase recusou a leitura (HTTP 500)."
    assert result.ignored == [Ignored(5, "sem motorista")]
    assert result.written == 0
    assert _posts() == []


@responses.activate
def test_sync_that_fails_while_sending_reports_what_was_written(tmp_path):
    responses.get(TABLE, json=STORED)
    responses.post(TABLE, status=201)
    responses.post(TABLE, status=401)

    result = sync(_sheet(tmp_path, ROWS), COLUMNS, CONFIG, now=NOW)

    assert result.written == 1
    assert result.error.startswith("A chave não tem permissão")
    assert SECRET not in result.error


@responses.activate
def test_sync_without_config_lists_what_is_missing(tmp_path):
    result = sync(_sheet(tmp_path, ROWS), COLUMNS, SyncConfig("", "", ""), now=NOW)

    assert result.error == "Falta preencher em enviar_planilha.env: SUPABASE_URL, SUPABASE_SECRET_KEY."
    assert len(responses.calls) == 0


@responses.activate
def test_sync_refuses_the_app_publishable_key(tmp_path):
    config = SyncConfig("https://example.supabase.co", "sb_publishable_abc", "")

    result = sync(_sheet(tmp_path, ROWS), COLUMNS, config, now=NOW)

    assert "publishable" in result.error
    assert "sb_publishable_abc" not in result.error
    assert len(responses.calls) == 0


def test_sync_result_defaults_describe_an_empty_run():
    result = SyncResult(finished_at=NOW)

    assert (result.new, result.updated, result.unchanged, result.written, result.ignored, result.error) == (
        0, 0, 0, 0, [], None,
    )
    assert result.finished_at.date() == date(2026, 11, 22)
