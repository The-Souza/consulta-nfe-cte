"""Reads the deliveries sheet: header on row 1 of the first sheet, one delivery per row below it."""
import shutil
import tempfile
import unicodedata
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Iterator

import openpyxl
from openpyxl.utils import column_index_from_string, get_column_letter


class _Invalid:
    def __repr__(self) -> str:
        return "INVALID"


INVALID = _Invalid()  # a value that is there but isn't a number/date (unlike an empty cell)


class SheetError(Exception):
    """The chosen file can't be read as a workbook. The message is shown on screen."""

FIELDS = ("nfe", "cte", "driver", "date")

# Header titles, compared without case, accents, spaces, hyphens and dots
_TITLES = {
    "nfe": {"nfe", "notafiscal"},
    "cte": {"cte"},
    "driver": {"motorista"},
    "date": {"data", "dataentrega", "datadeentrega"},
}


@dataclass(frozen=True)
class Columns:
    """Column letters ("A", "D") of each field. The CT-e column is optional."""
    nfe: str
    driver: str
    date: str
    cte: str | None = None


@dataclass(frozen=True)
class Entry:
    nfe: int | None
    cte: int | None
    driver: str
    date: date | None
    line: int  # row number in the sheet, as Excel shows it


@dataclass(frozen=True)
class Ignored:
    line: int
    reason: str


def parse_number(value) -> int | None | _Invalid:
    """NF-e or CT-e: digits only, without leading zeros. Excel may keep a typed number as 4516661.0."""
    if value is None:
        return None
    if isinstance(value, bool):
        return INVALID
    if isinstance(value, float):
        if not value.is_integer():
            return INVALID
        value = int(value)
    if isinstance(value, int):
        return value if value > 0 else INVALID
    text = str(value).strip()
    if not text:
        return None
    # isdigit() alone also accepts Unicode digits like "²", which int() rejects
    if not (text.isascii() and text.isdigit()) or int(text) == 0:
        return INVALID
    return int(text)


def parse_date(value) -> date | None | _Invalid:
    """A date cell, or text typed as dd/mm/aaaa. strptime rejects impossible days like 31/02."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if not isinstance(value, str):
        return INVALID
    text = value.strip()
    if not text:
        return None
    try:
        return datetime.strptime(text, "%d/%m/%Y").date()
    except ValueError:
        return INVALID


def _plain(title: str) -> str:
    decomposed = unicodedata.normalize("NFKD", title.casefold())
    letters = "".join(c for c in decomposed if not unicodedata.combining(c))
    return "".join(c for c in letters if c not in " -._")


def suggest_columns(headers: list[tuple[str, str]]) -> dict[str, str | None]:
    """First guess of the columns from the header titles. A field with no matching title stays None."""
    suggestion: dict[str, str | None] = dict.fromkeys(FIELDS)
    for letter, title in headers:
        plain = _plain(title)
        for name in FIELDS:
            if suggestion[name] is None and plain in _TITLES[name]:
                suggestion[name] = letter
    return suggestion


@contextmanager
def _open_copy(path: Path) -> Iterator:
    """The first sheet of a copy of the file. Excel keeps the original locked while it is open, and the
    original is never opened by us, so it can't be changed or locked by a read."""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as folder:
        copy = Path(folder) / "planilha.xlsx"
        shutil.copy2(path, copy)
        # Our own handle: a load that fails halfway can keep openpyxl's reader alive in a reference cycle,
        # and the zip reader never closes a file it was given. Closing it here releases the copy on every
        # path, so the temporary folder can be removed.
        with open(copy, "rb") as stream:
            workbook = _load(stream)
            try:
                yield workbook.worksheets[0]
            finally:
                workbook.close()


def _load(stream):
    try:
        return openpyxl.load_workbook(stream, read_only=True, data_only=True)
    except Exception as error:  # openpyxl raises many types for a file that isn't a workbook (zip, XML, keys)
        raise SheetError("O arquivo não é uma planilha .xlsx válida.") from error


def read_headers(path: Path) -> list[tuple[str, str]]:
    with _open_copy(path) as sheet:
        first = next(sheet.iter_rows(min_row=1, max_row=1, values_only=True), ())
    return [(get_column_letter(i + 1), "" if v is None else str(v).strip()) for i, v in enumerate(first)]


def _blank(value) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def _cell(row: tuple, letter: str | None):
    if letter is None:
        return None
    index = column_index_from_string(letter) - 1
    return row[index] if index < len(row) else None


def _parse_row(row: tuple, line: int, columns: Columns) -> Entry | Ignored:
    nfe = parse_number(_cell(row, columns.nfe))
    cte = parse_number(_cell(row, columns.cte))
    if nfe is INVALID:
        return Ignored(line, "NF-e com texto")
    if cte is INVALID:
        return Ignored(line, "CT-e com texto")
    if nfe is None and cte is None:
        return Ignored(line, "sem NF-e nem CT-e")
    driver = _cell(row, columns.driver)
    if _blank(driver):
        return Ignored(line, "sem motorista")
    delivered = parse_date(_cell(row, columns.date))
    if delivered is INVALID:
        return Ignored(line, "data inválida")
    return Entry(nfe=nfe, cte=cte, driver=str(driver).strip(), date=delivered, line=line)


def read_entries(path: Path, columns: Columns) -> tuple[list[Entry], list[Ignored]]:
    """Valid rows and ignored rows with the reason. A repeated NF-e (or CT-e of a row without NF-e)
    counts by its last row; the earlier ones are ignored."""
    parsed: list[Entry] = []
    ignored: list[Ignored] = []
    with _open_copy(path) as sheet:
        for line, row in enumerate(sheet.iter_rows(min_row=2, values_only=True), start=2):
            if all(_blank(v) for v in row):  # Excel often keeps formatted empty rows at the end
                continue
            result = _parse_row(row, line, columns)
            (parsed if isinstance(result, Entry) else ignored).append(result)

    def key(entry: Entry) -> tuple[str, int]:
        return ("nfe", entry.nfe) if entry.nfe is not None else ("cte", entry.cte)

    last = {key(e): e.line for e in parsed}
    entries = [e for e in parsed if last[key(e)] == e.line]
    ignored += [Ignored(e.line, f"repetida na linha {last[key(e)]}") for e in parsed if last[key(e)] != e.line]
    return entries, sorted(ignored, key=lambda i: i.line)
