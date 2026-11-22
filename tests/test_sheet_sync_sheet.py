import hashlib
import os
import tempfile
from datetime import date, datetime

import openpyxl
import pytest

from sheet_sync.sheet import (
    INVALID,
    Columns,
    Entry,
    Ignored,
    parse_date,
    parse_number,
    read_entries,
    read_headers,
    suggest_columns,
)

HEADERS = ["Motorista", "Data", "NFe", "Cliente", "Destinatário", "CTe"]
COLUMNS = Columns(nfe="C", driver="A", date="B", cte="F")


def _sheet(tmp_path, rows, headers=HEADERS, name="entregas.xlsx"):
    """A workbook like the real one: header on row 1, data from row 2. Fictitious data only."""
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.append(headers)
    for row in rows:
        sheet.append(row)
    path = tmp_path / name
    workbook.save(path)
    return path


# parse_number -----------------------------------------------------------------

@pytest.mark.parametrize(("value", "expected"), [
    (4516661, 4516661),
    (4516661.0, 4516661),
    ("4516661", 4516661),
    ("  4516661 ", 4516661),
    ("0004516661", 4516661),
    (None, None),
    ("", None),
    ("   ", None),
    ("NF 4516661", INVALID),
    ("abc", INVALID),
    (4516661.5, INVALID),
    (0, INVALID),
    ("000", INVALID),
    (-5, INVALID),
    (True, INVALID),
])
def test_parse_number(value, expected):
    assert parse_number(value) == expected


# parse_date -------------------------------------------------------------------

@pytest.mark.parametrize(("value", "expected"), [
    (datetime(2026, 11, 22, 0, 0), date(2026, 11, 22)),
    (date(2026, 11, 22), date(2026, 11, 22)),
    ("22/11/2026", date(2026, 11, 22)),
    (" 22/11/2026 ", date(2026, 11, 22)),
    (None, None),
    ("", None),
    ("31/02/2026", INVALID),
    ("amanhã", INVALID),
    ("2026-11-22", INVALID),
    (46348, INVALID),
])
def test_parse_date(value, expected):
    assert parse_date(value) == expected


# suggest_columns --------------------------------------------------------------

def test_suggest_columns_from_the_real_header_titles():
    headers = [("A", "Motorista"), ("B", "Data"), ("C", "NFe"), ("D", "Cliente"), ("E", "Destinatário"), ("F", "CTe")]

    assert suggest_columns(headers) == {"nfe": "C", "cte": "F", "driver": "A", "date": "B"}


def test_suggest_columns_ignores_case_accents_and_punctuation():
    headers = [("A", "NOTA FISCAL"), ("B", "Data de Entrega"), ("C", "CT-e"), ("D", "motorista ")]

    assert suggest_columns(headers) == {"nfe": "A", "cte": "C", "driver": "D", "date": "B"}


def test_suggest_columns_leaves_unmatched_fields_empty():
    headers = [("A", "Nota"), ("B", "Entregador")]

    assert suggest_columns(headers) == {"nfe": None, "cte": None, "driver": None, "date": None}


# read_headers -----------------------------------------------------------------

def test_read_headers_lists_letter_and_title(tmp_path):
    path = _sheet(tmp_path, [], headers=["Motorista", None, "NFe"])

    assert read_headers(path) == [("A", "Motorista"), ("B", ""), ("C", "NFe")]


# read_entries -----------------------------------------------------------------

def test_read_entries_normalizes_each_row(tmp_path):
    path = _sheet(tmp_path, [
        ["Ana Souza ", datetime(2026, 11, 22), 4516661, "Cliente X", "Destino Y", 25540],
        ["Bia", "21/11/2026", "0004516662", None, None, None],
        ["Caio", None, None, None, None, "5533"],
    ])

    entries, ignored = read_entries(path, COLUMNS)

    assert entries == [
        Entry(nfe=4516661, cte=25540, driver="Ana Souza", date=date(2026, 11, 22), line=2),
        Entry(nfe=4516662, cte=None, driver="Bia", date=date(2026, 11, 21), line=3),
        Entry(nfe=None, cte=5533, driver="Caio", date=None, line=4),
    ]
    assert ignored == []


def test_read_entries_without_a_cte_column(tmp_path):
    path = _sheet(tmp_path, [["Ana", None, 4516661, None, None, 25540]])

    entries, _ = read_entries(path, Columns(nfe="C", driver="A", date="B"))

    assert entries == [Entry(nfe=4516661, cte=None, driver="Ana", date=None, line=2)]


def test_read_entries_ignores_invalid_rows_with_line_and_reason(tmp_path):
    path = _sheet(tmp_path, [
        ["Ana", None, None, None, None, None],          # 2
        ["Ana", None, "NF 123", None, None, None],      # 3
        ["Ana", None, 123, None, None, "abc"],          # 4
        [None, None, 124, None, None, None],            # 5
        ["  ", None, 125, None, None, None],            # 6
        ["Ana", "amanhã", 126, None, None, None],       # 7
        ["Ana", "31/02/2026", 127, None, None, None],   # 8
        ["Ana", None, 128, None, None, None],           # 9: valid
    ])

    entries, ignored = read_entries(path, COLUMNS)

    assert [e.line for e in entries] == [9]
    assert ignored == [
        Ignored(2, "sem NF-e nem CT-e"),
        Ignored(3, "NF-e com texto"),
        Ignored(4, "CT-e com texto"),
        Ignored(5, "sem motorista"),
        Ignored(6, "sem motorista"),
        Ignored(7, "data inválida"),
        Ignored(8, "data inválida"),
    ]


def test_read_entries_keeps_the_last_of_repeated_invoices(tmp_path):
    path = _sheet(tmp_path, [
        ["Ana", None, 100, None, None, None],   # 2
        ["Bia", None, 100, None, None, None],   # 3
        ["Caio", None, 200, None, None, None],  # 4
        ["Davi", None, 100, None, None, None],  # 5: the one that counts for 100
    ])

    entries, ignored = read_entries(path, COLUMNS)

    assert [(e.nfe, e.driver) for e in entries] == [(200, "Caio"), (100, "Davi")]
    assert ignored == [Ignored(2, "repetida na linha 5"), Ignored(3, "repetida na linha 5")]


def test_read_entries_repeated_cte_only_rows_keep_the_last(tmp_path):
    path = _sheet(tmp_path, [
        ["Ana", None, None, None, None, 5533],
        ["Bia", None, None, None, None, 5533],
        ["Caio", None, 300, None, None, 5533],  # has an NF-e: not a repetition of the load row
    ])

    entries, ignored = read_entries(path, COLUMNS)

    assert [(e.nfe, e.cte, e.driver) for e in entries] == [(None, 5533, "Bia"), (300, 5533, "Caio")]
    assert ignored == [Ignored(2, "repetida na linha 3")]


def test_read_entries_skips_blank_rows_silently(tmp_path):
    path = _sheet(tmp_path, [
        ["Ana", None, 100, None, None, None],
        [None, None, None, None, None, None],
        ["", "  ", None, None, None, None],
        ["Bia", None, 101, None, None, None],
    ])

    entries, ignored = read_entries(path, COLUMNS)

    assert [e.line for e in entries] == [2, 5]
    assert ignored == []


def test_read_entries_reads_a_copy_and_leaves_no_temporary_file(tmp_path, monkeypatch):
    path = _sheet(tmp_path, [["Ana", None, 100, None, None, None]])
    before = (hashlib.sha256(path.read_bytes()).hexdigest(), os.stat(path).st_mtime_ns)
    temp_dir = tmp_path / "temp"
    temp_dir.mkdir()
    monkeypatch.setattr(tempfile, "tempdir", str(temp_dir))

    read_entries(path, COLUMNS)
    read_headers(path)

    assert (hashlib.sha256(path.read_bytes()).hexdigest(), os.stat(path).st_mtime_ns) == before
    assert list(temp_dir.iterdir()) == []
