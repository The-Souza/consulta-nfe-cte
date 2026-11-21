"""Filters, counts and texts of the search screen, kept out of the UI so they can be tested.

A result row is the dict built by the search worker: {"NF-e", "CT-e", "Imagem", "Status", "Motorista", "Entrega"}.
"""

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date
from typing import Callable

from utils.status import CONNECTION_FAILED, SEARCH_NO_CTE, SEARCH_NOT_FOUND, SEARCH_OK

Row = dict
_NO_CTE = ("-", "")

NO_DRIVER = ""  # "Motorista" of an invoice that isn't in the drivers sheet
NO_DRIVER_LABEL = "Sem motorista na planilha"

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


def visible_rows(rows: list[Row], chip: str, cte: str | None = None, driver: str | None = None) -> list[Row]:
    """Rows shown in the table, in query order. A selected CT-e takes precedence over the chip;
    a selected driver narrows the chip (NO_DRIVER picks the invoices outside the sheet)."""
    if cte is not None:
        return [r for r in rows if r["CT-e"] == cte]
    predicate = _PREDICATES[chip]
    return [r for r in rows if predicate(r) and (driver is None or r["Motorista"] == driver)]


@dataclass(frozen=True)
class DriverGroup:
    driver: str
    count: int
    dates: list[date] = field(default_factory=list)  # unique delivery dates, in order


def driver_groups(rows: list[Row]) -> list[DriverGroup]:
    """Invoices per driver for the side panel: most invoices first, ties by name, and the invoices
    outside the sheet always last."""
    counts: Counter[str] = Counter()
    dates: dict[str, set[date]] = defaultdict(set)
    for r in rows:
        counts[r["Motorista"]] += 1
        if r["Entrega"]:
            dates[r["Motorista"]].add(r["Entrega"])
    groups = [DriverGroup(driver, count, sorted(dates[driver])) for driver, count in counts.items()]
    return sorted(groups, key=lambda g: (g.driver == NO_DRIVER, -g.count, g.driver.casefold()))


def driver_filter_text(count: int, driver: str, chip: str) -> str:
    """Filter bar above the table while a driver is picked in the side panel."""
    shown = f"Mostrando {_count(count, 'NF-e', 'NF-es')}"
    no_image = chip == "no_image"
    if driver == NO_DRIVER:
        return f"{shown} {'sem imagem e ' if no_image else ''}sem motorista na planilha"
    return f"{shown} de {driver}{' sem imagem' if no_image else ''}"


def cte_multiplicity(rows: list[Row]) -> dict[str, int]:
    """How many invoices of the query share each CT-e (for the "×N" mark)."""
    return dict(Counter(r["CT-e"] for r in rows if r["CT-e"] not in _NO_CTE))


def cte_counts(rows: list[Row]) -> list[tuple[str, int]]:
    """CT-es of the query with how many invoices each one groups, most invoices first.
    Ties follow the CT-e number, so the panel order doesn't change between redraws."""
    def order(item: tuple[str, int]) -> tuple:
        cte, count = item
        number = (0, int(cte), "") if cte.isdigit() else (1, 0, cte)
        return (-count, *number)

    return sorted(cte_multiplicity(rows).items(), key=order)


def _count(n: int, singular: str, plural: str) -> str:
    return f"{n:,}".replace(",", ".") + " " + (singular if n == 1 else plural)


def status_text(total: int, failures: int, elapsed: float) -> str:
    minutes, seconds = divmod(int(elapsed), 60)
    parts = ["Consulta concluída", _count(total, "NF-e", "NF-es")]
    if failures:
        parts.append(f"{failures} com falha")
    parts.append(f"{minutes:02d}:{seconds:02d}")
    return " · ".join(parts)
