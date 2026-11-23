from datetime import datetime, timedelta, timezone

import pytest

from sheet_sync.report import NO_COLUMN, column_options, count_label, ignored_lines, letter_of, sent_label
from sheet_sync.sheet import Ignored

LOCAL = timezone(timedelta(hours=-3))
NOW = datetime(2026, 11, 23, 15, 0, tzinfo=LOCAL)


# sent_label -----------------------------------------------------------------------

@pytest.mark.parametrize(("when", "expected"), [
    (datetime(2026, 11, 23, 17, 20, tzinfo=timezone.utc), "hoje às 14:20"),
    (datetime(2026, 11, 22, 12, 5, tzinfo=timezone.utc), "ontem às 09:05"),
    (datetime(2026, 11, 12, 12, 5, tzinfo=timezone.utc), "12/11 às 09:05"),
    (datetime(2025, 11, 12, 12, 5, tzinfo=timezone.utc), "12/11/2025 às 09:05"),
])
def test_sent_label_uses_the_local_day(when, expected):
    assert sent_label(when, NOW) == expected


def test_sent_label_converts_utc_before_comparing_days():
    # 01:30 UTC on the 24th is still 22:30 of the 23rd in UTC-3
    assert sent_label(datetime(2026, 11, 24, 1, 30, tzinfo=timezone.utc), NOW) == "hoje às 22:30"


# count_label ----------------------------------------------------------------------

@pytest.mark.parametrize(("kind", "count", "expected"), [
    ("new", 1, "nova"),
    ("new", 214, "novas"),
    ("new", 0, "novas"),
    ("updated", 1, "atualizada"),
    ("updated", 37, "atualizadas"),
    ("ignored", 1, "linha ignorada"),
    ("ignored", 3, "linhas ignoradas"),
])
def test_count_label(kind, count, expected):
    assert count_label(kind, count) == expected


# ignored_lines --------------------------------------------------------------------

def test_ignored_lines_groups_by_reason_in_order_of_first_line():
    ignored = [Ignored(4, "sem motorista"), Ignored(10488, "NF-e com texto"), Ignored(10491, "NF-e com texto"),
               Ignored(10502, "NF-e com texto")]

    assert ignored_lines(ignored) == [
        "Sem motorista (linha 4).",
        "NF-e com texto (linhas 10.488, 10.491 e 10.502).",
    ]


def test_ignored_lines_shows_at_most_ten_lines_per_reason():
    ignored = [Ignored(line, "data inválida") for line in range(2, 15)]

    assert ignored_lines(ignored) == ["Data inválida (linhas 2, 3, 4, 5, 6, 7, 8, 9, 10, 11 e mais 3)."]


def test_ignored_lines_without_ignored_rows():
    assert ignored_lines([]) == []


# column options -------------------------------------------------------------------

def test_column_options_show_letter_and_title():
    headers = [("A", "Motorista"), ("B", ""), ("C", "NFe")]

    assert column_options(headers) == ["A · Motorista", "B", "C · NFe"]


@pytest.mark.parametrize(("option", "expected"), [
    ("D · Nota fiscal", "D"),
    ("AB · Data", "AB"),
    ("B", "B"),
    (NO_COLUMN, None),
    ("", None),
])
def test_letter_of_reads_the_column_back(option, expected):
    assert letter_of(option) == expected
