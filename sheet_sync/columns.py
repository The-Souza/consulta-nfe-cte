"""Which sheet column holds each field. A column is tracked by its header title, since inserting a column in
Excel moves the titles but keeps the letters: a choice made by letter alone would send the wrong data."""
from collections import Counter

from sheet_sync.sheet import FIELDS, Columns, suggest_columns

_REQUIRED = ("nfe", "driver", "date")


def _unique_titles(headers: list[tuple[str, str]]) -> dict[str, str]:
    """Title -> letter, only for titles that show up once: a repeated or empty title can't tell which column
    it was."""
    counts = Counter(title for _, title in headers)
    return {title: letter for letter, title in headers if title and counts[title] == 1}


def saved_columns_valid(headers: list[tuple[str, str]], saved: dict[str, str | None],
                        saved_titles: dict[str, str]) -> bool:
    """The saved choice still points at the same columns: every chosen letter still has the title it was
    chosen by. Only then may the automatic send go on without the user looking at the columns."""
    current = dict(headers)
    return all(saved.get(f) for f in _REQUIRED) and all(
        letter is None or (letter in current and current[letter] == saved_titles.get(field))
        for field, letter in saved.items()
    )


def choose_columns(headers: list[tuple[str, str]], saved: dict[str, str | None], saved_titles: dict[str, str],
                   keep: bool) -> dict[str, str | None]:
    """The column of each field for the menus. With `keep` (the same sheet opened again), the saved choice
    stays while each column keeps its title; otherwise each saved title is followed to its new letter and
    the rest is suggested from the titles. A CT-e saved as no column stays without one."""
    if keep and saved_columns_valid(headers, saved, saved_titles):
        return {field: saved.get(field) for field in FIELDS}

    chosen = suggest_columns(headers)
    if keep:
        by_title = _unique_titles(headers)
        for field, title in saved_titles.items():
            if field in chosen and title in by_title:
                chosen[field] = by_title[title]
        if "cte" in saved and saved["cte"] is None:
            chosen["cte"] = None
    return chosen


def ambiguous_columns(headers: list[tuple[str, str]], columns: Columns) -> list[str]:
    """Chosen fields whose column has an empty or repeated title. Their title can't prove the column didn't
    move, so they block a send until the sheet gives them a unique title."""
    counts = Counter(title for _, title in headers)
    current = dict(headers)
    ambiguous = []
    for field in FIELDS:
        letter = getattr(columns, field)
        if letter is None:
            continue
        title = current.get(letter, "")
        if not title or counts[title] > 1:
            ambiguous.append(field)
    return ambiguous
