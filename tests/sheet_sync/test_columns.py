import pytest

from sheet_sync.columns import ambiguous_columns, choose_columns, saved_columns_valid
from sheet_sync.sheet import Columns

# Hand-picked columns whose titles the automatic suggestion wouldn't match
SAVED = {"nfe": "C", "driver": "A", "date": "B", "cte": None}
TITLES = {"nfe": "Nota", "driver": "Entregador", "date": "Dia"}
HEADERS = [("A", "Entregador"), ("B", "Dia"), ("C", "Nota")]


# choose_columns ------------------------------------------------------------------

def test_keeps_the_saved_columns_while_letters_and_titles_match():
    assert choose_columns(HEADERS, SAVED, TITLES, keep=True) == SAVED


def test_follows_each_saved_title_to_its_new_letter_after_a_column_is_inserted():
    headers = [("A", "Entregador"), ("B", "Cliente"), ("C", "Dia"), ("D", "Nota")]

    assert choose_columns(headers, SAVED, TITLES, keep=True) == {"nfe": "D", "driver": "A", "date": "C", "cte": None}


def test_does_not_follow_a_title_that_now_repeats():
    # Two "Dia" columns: which one was chosen can't be told, so the field is left for the user
    headers = [("A", "Entregador"), ("B", "Dia"), ("C", "Dia"), ("D", "Nota")]

    assert choose_columns(headers, SAVED, TITLES, keep=True)["date"] is None


def test_does_not_follow_an_empty_title():
    headers = [("A", "Entregador"), ("B", "Cliente"), ("C", ""), ("D", "Nota")]

    assert choose_columns(headers, SAVED, {**TITLES, "date": ""}, keep=True)["date"] is None


def test_unmatched_fields_fall_back_to_the_suggestion():
    headers = [("A", "Motorista"), ("B", "Data"), ("C", "NFe"), ("D", "CTe")]

    assert choose_columns(headers, SAVED, TITLES, keep=True) == {"nfe": "C", "driver": "A", "date": "B", "cte": None}


def test_a_cte_left_as_none_stays_none_when_the_columns_are_chosen_again():
    headers = [("A", "Entregador"), ("B", "Cliente"), ("C", "Dia"), ("D", "Nota"), ("E", "CTe")]

    assert choose_columns(headers, SAVED, TITLES, keep=True)["cte"] is None


def test_prefs_without_titles_are_suggested_again():
    headers = [("A", "Motorista"), ("B", "Data"), ("C", "NFe")]

    assert choose_columns(headers, SAVED, {}, keep=True) == {"nfe": "C", "driver": "A", "date": "B", "cte": None}


def test_a_new_sheet_ignores_the_saved_columns():
    headers = [("A", "NFe"), ("B", "Motorista"), ("C", "Data"), ("D", "CTe")]

    assert choose_columns(headers, SAVED, TITLES, keep=False) == {"nfe": "A", "driver": "B", "date": "C", "cte": "D"}


def test_without_a_header_nothing_is_chosen():
    assert choose_columns([], SAVED, TITLES, keep=True) == {"nfe": None, "driver": None, "date": None, "cte": None}


# saved_columns_valid -------------------------------------------------------------
# Decides whether the automatic send may go on with the saved columns, or must wait for the user

@pytest.mark.parametrize(("headers", "saved", "titles", "expected"), [
    (HEADERS, SAVED, TITLES, True),
    ([("A", "Entregador"), ("B", "Cliente"), ("C", "Dia"), ("D", "Nota")], SAVED, TITLES, False),  # moved
    ([("A", "Entregador"), ("B", "Entregue em"), ("C", "Nota")], SAVED, TITLES, False),  # renamed
    (HEADERS, SAVED, {}, False),  # saved before titles existed
    (HEADERS, {}, {}, False),  # nothing saved yet
    ([], SAVED, TITLES, False),  # sheet not read
    (HEADERS + [("D", "CTe")], {**SAVED, "cte": "D"}, {**TITLES, "cte": "CTe"}, True),
])
def test_saved_columns_valid(headers, saved, titles, expected):
    assert saved_columns_valid(headers, saved, titles) is expected


# ambiguous_columns ---------------------------------------------------------------

COLUMNS = Columns(nfe="C", driver="A", date="B")


def test_unique_titles_are_not_ambiguous():
    assert ambiguous_columns(HEADERS, COLUMNS) == []


def test_a_repeated_title_is_ambiguous():
    headers = [("A", "Entregador"), ("B", "Dia"), ("C", "Nota"), ("D", "Dia")]

    assert ambiguous_columns(headers, COLUMNS) == ["date"]


def test_an_empty_title_is_ambiguous():
    headers = [("A", ""), ("B", "Dia"), ("C", "Nota")]

    assert ambiguous_columns(headers, COLUMNS) == ["driver"]


def test_a_cte_left_as_none_is_not_checked():
    headers = [("A", "Entregador"), ("B", "Dia"), ("C", "Nota"), ("D", ""), ("E", "")]

    assert ambiguous_columns(headers, COLUMNS) == []
