import time

import pytest

from utils.nfe_query import MAX_INVOICES, parse_query

INVALID = "Formato não reconhecido"


# valid input ------------------------------------------------------------------------

@pytest.mark.parametrize("text", ["4516661", "  4516661  ", "\t4516661\n"])
def test_single_invoice(text):
    parsed = parse_query(text)

    assert parsed.valid
    assert parsed.invoices == [4516661]
    assert parsed.label == "1 NF-e"


def test_range():
    parsed = parse_query("4516661-4516680")

    assert parsed.valid
    assert parsed.invoices == list(range(4516661, 4516681))
    assert parsed.label == "Faixa · 20 NF-es"


@pytest.mark.parametrize("text", ["4516661 - 4516680", "4516661 -4516680", "4516661-  4516680"])
def test_range_with_spaces_around_the_hyphen(text):
    parsed = parse_query(text)

    assert parsed.invoices == list(range(4516661, 4516681))
    assert parsed.label == "Faixa · 20 NF-es"


def test_ranges_with_spaces_inside_a_list():
    assert parse_query("1 - 3, 10").invoices == [1, 2, 3, 10]


def test_range_of_one_is_a_single_invoice():
    parsed = parse_query("4516661-4516661")

    assert parsed.invoices == [4516661]
    assert parsed.label == "1 NF-e"


@pytest.mark.parametrize("text", ["1, 2, 3", "1;2;3", "1 2 3", "1\n2\n3", "1,\r\n2 ;\t3", "1,,2;;3"])
def test_list_with_any_separator(text):
    parsed = parse_query(text)

    assert parsed.invoices == [1, 2, 3]
    assert parsed.label == "Lista · 3 NF-es"


def test_range_inside_a_list():
    parsed = parse_query("1-3, 10")

    assert parsed.invoices == [1, 2, 3, 10]
    assert parsed.label == "Lista · 4 NF-es"


def test_repeated_invoices_are_queried_once_in_first_order():
    parsed = parse_query("5, 1, 5, 2-3, 1")

    assert parsed.invoices == [5, 1, 2, 3]
    assert parsed.label == "Lista · 4 NF-es"


def test_leading_zeros_are_ignored():
    assert parse_query("00123").invoices == [123]


# empty and invalid ------------------------------------------------------------------

@pytest.mark.parametrize("text", ["", "   ", "\n", ", ;"])
def test_empty_text_has_no_label(text):
    parsed = parse_query(text)

    assert not parsed.valid
    assert parsed.invoices == []
    assert parsed.label == ""


@pytest.mark.parametrize("text", ["abc", "12a", "1-", "-5", "20-10", "1--5", "1-2-3", "1, x", "4516661.0"])
def test_invalid_format(text):
    parsed = parse_query(text)

    assert not parsed.valid
    assert parsed.invoices == []
    assert parsed.label == INVALID


# limits -----------------------------------------------------------------------------

def test_maximum_is_accepted():
    parsed = parse_query(f"1-{MAX_INVOICES}")

    assert parsed.valid
    assert len(parsed.invoices) == MAX_INVOICES


def test_above_maximum_is_refused():
    parsed = parse_query("1-200, 9000")

    assert not parsed.valid
    assert parsed.invoices == []
    assert parsed.label == "Máximo de 200 NF-es por consulta"


def test_repeated_numbers_count_once_toward_the_limit():
    parsed = parse_query("1-200, 5, 200")

    assert parsed.valid
    assert len(parsed.invoices) == 200


def test_huge_range_is_refused_without_building_the_list():
    start = time.perf_counter()

    parsed = parse_query("1-999999999")

    assert not parsed.valid
    assert time.perf_counter() - start < 0.1
