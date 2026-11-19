import pytest

from utils.search_results import CHIPS, chip_counts, cte_counts, cte_multiplicity, status_text, visible_rows
from utils.status import CONNECTION_FAILED, SEARCH_NO_CTE, SEARCH_NOT_FOUND, SEARCH_OK


def row(nfe, status=SEARCH_OK, cte="-", image="Sim"):
    return {"NF-e": nfe, "CT-e": cte, "Imagem": image, "Status": status}


ROWS = [
    row(1, SEARCH_OK, "100", "Sim"),
    row(2, SEARCH_OK, "100", "Não"),
    row(3, SEARCH_OK, "200", "Sim"),
    row(4, SEARCH_NO_CTE, "-", "Não"),
    row(5, SEARCH_NOT_FOUND, "-", "-"),
    row(6, CONNECTION_FAILED, "-", "-"),
    row(7, "Erro 404", "-", "-"),
]


def nfes(rows):
    return [r["NF-e"] for r in rows]


# chips ------------------------------------------------------------------------------

def test_chip_order_and_labels():
    assert [(key, label) for key, label, _ in CHIPS] == [
        ("all", "Todos"),
        ("ok", "Com CT-e"),
        ("no_cte", "Sem CT-e"),
        ("not_found", "Não cadastrada"),
        ("no_image", "Sem imagem"),
        ("connection", "Falha de conexão"),
    ]


@pytest.mark.parametrize(
    ("chip", "expected"),
    [
        ("all", [1, 2, 3, 4, 5, 6, 7]),
        ("ok", [1, 2, 3]),
        ("no_cte", [4]),
        ("not_found", [5]),
        ("no_image", [2, 4]),
        ("connection", [6]),
    ],
)
def test_visible_rows_by_chip_keep_query_order(chip, expected):
    assert nfes(visible_rows(ROWS, chip)) == expected


def test_other_errors_only_show_in_all():
    other = [chip for chip, _, _ in CHIPS if chip != "all"]

    assert all(7 not in nfes(visible_rows(ROWS, chip)) for chip in other)


def test_chip_counts():
    assert chip_counts(ROWS) == {
        "all": 7, "ok": 3, "no_cte": 1, "not_found": 1, "no_image": 2, "connection": 1,
    }


def test_chip_counts_without_rows():
    assert chip_counts([]) == {key: 0 for key, _, _ in CHIPS}


def test_unknown_chip_raises():
    with pytest.raises(KeyError):
        visible_rows(ROWS, "missing")


# cte filter -------------------------------------------------------------------------

def test_cte_filter_ignores_the_chip():
    assert nfes(visible_rows(ROWS, "connection", cte="100")) == [1, 2]


def test_cte_filter_with_unknown_cte_is_empty():
    assert visible_rows(ROWS, "all", cte="999") == []


# multiplicity -----------------------------------------------------------------------

def test_cte_multiplicity_counts_invoices_per_cte():
    assert cte_multiplicity(ROWS) == {"100": 2, "200": 1}


def test_cte_multiplicity_ignores_missing_cte():
    assert cte_multiplicity([row(1, cte="-"), row(2, cte="")]) == {}


# cte counts (side panel) ------------------------------------------------------------

def test_cte_counts_sorted_by_quantity():
    rows = [row(1, cte="200"), row(2, cte="100"), row(3, cte="100"), row(4, cte="300"), row(5, cte="100")]

    assert cte_counts(rows) == [("100", 3), ("200", 1), ("300", 1)]


def test_cte_counts_break_ties_by_cte_number():
    rows = [row(1, cte="25541"), row(2, cte="5533"), row(3, cte="25540")]

    assert cte_counts(rows) == [("5533", 1), ("25540", 1), ("25541", 1)]


def test_cte_counts_ignore_invoices_without_cte():
    assert cte_counts(ROWS) == [("100", 2), ("200", 1)]


def test_cte_counts_without_rows():
    assert cte_counts([]) == []


# status text ------------------------------------------------------------------------

@pytest.mark.parametrize(
    ("total", "failures", "elapsed", "expected"),
    [
        (20, 0, 41.9, "Consulta concluída · 20 NF-es · 00:41"),
        (20, 2, 41, "Consulta concluída · 20 NF-es · 2 com falha · 00:41"),
        (1, 0, 3, "Consulta concluída · 1 NF-e · 00:03"),
        (1200, 1, 3725, "Consulta concluída · 1.200 NF-es · 1 com falha · 62:05"),
    ],
)
def test_status_text(total, failures, elapsed, expected):
    assert status_text(total, failures, elapsed) == expected
