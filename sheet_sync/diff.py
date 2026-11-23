"""Compares the sheet with the entregas table, so only new and changed rows are written."""
from dataclasses import dataclass
from datetime import date

from sheet_sync.sheet import Entry


@dataclass(frozen=True)
class Stored:
    """A row of the entregas table."""
    id: str
    nfe: int | None
    cte: int | None
    driver: str
    date: date | None


@dataclass(frozen=True)
class Changes:
    new: list[Entry]
    updated: list[tuple[str, Entry]]  # (table id, sheet row)
    unchanged: int


def compare(entries: list[Entry], stored: list[Stored]) -> Changes:
    """An invoice row matches the table row with the same NF-e. A load row (CT-e without NF-e) matches the
    table row with the same CT-e and no NF-e, like the table's unique indexes. Table rows missing from the
    sheet are left alone: nothing is ever deleted."""
    by_nfe = {s.nfe: s for s in stored if s.nfe is not None}
    loads = {s.cte: s for s in stored if s.nfe is None}

    new: list[Entry] = []
    updated: list[tuple[str, Entry]] = []
    unchanged = 0
    for entry in entries:
        match = by_nfe.get(entry.nfe) if entry.nfe is not None else loads.get(entry.cte)
        if match is None:
            new.append(entry)
        elif (match.driver, match.date, match.cte) != (entry.driver, entry.date, entry.cte):
            updated.append((match.id, entry))
        else:
            unchanged += 1
    return Changes(new=new, updated=updated, unchanged=unchanged)
