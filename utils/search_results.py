"""Filters, counts and texts of the search screen, kept out of the UI so they can be tested.

A result row is the dict built by the search worker: {"NF-e", "CT-e", "Imagem", "Status"}.
"""

from collections import Counter
from typing import Callable

from utils.status import CONNECTION_FAILED, SEARCH_NO_CTE, SEARCH_NOT_FOUND, SEARCH_OK

Row = dict
_NO_CTE = ("-", "")

CHIPS: list[tuple[str, str, Callable[[Row], bool]]] = [
    ("all",        "Todos",            lambda r: True),
    ("ok",         "Com CT-e",         lambda r: r["Status"] == SEARCH_OK),
    ("no_cte",     "Sem CT-e",         lambda r: r["Status"] == SEARCH_NO_CTE),
    ("not_found",  "Não cadastrada",   lambda r: r["Status"] == SEARCH_NOT_FOUND),
    ("no_image",   "Sem imagem",       lambda r: r.get("Imagem") == "Não"),
    ("connection", "Falha de conexão", lambda r: r["Status"] == CONNECTION_FAILED),
]
_PREDICATES = {key: predicate for key, _, predicate in CHIPS}


def chip_counts(rows: list[Row]) -> dict[str, int]:
    return {key: sum(1 for r in rows if predicate(r)) for key, predicate in _PREDICATES.items()}


def visible_rows(rows: list[Row], chip: str, cte: str | None = None) -> list[Row]:
    """Rows shown in the table, in query order. A selected CT-e takes precedence over the chip."""
    if cte is not None:
        return [r for r in rows if r["CT-e"] == cte]
    predicate = _PREDICATES[chip]
    return [r for r in rows if predicate(r)]


def cte_multiplicity(rows: list[Row]) -> dict[str, int]:
    """How many invoices of the query share each CT-e (for the "×N" mark)."""
    return dict(Counter(r["CT-e"] for r in rows if r["CT-e"] not in _NO_CTE))


def _count(n: int, singular: str, plural: str) -> str:
    return f"{n:,}".replace(",", ".") + " " + (singular if n == 1 else plural)


def status_text(total: int, failures: int, elapsed: float) -> str:
    minutes, seconds = divmod(int(elapsed), 60)
    parts = ["Consulta concluída", _count(total, "NF-e", "NF-es")]
    if failures:
        parts.append(f"{failures} com falha")
    parts.append(f"{minutes:02d}:{seconds:02d}")
    return " · ".join(parts)
