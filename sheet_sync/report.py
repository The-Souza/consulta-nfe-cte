"""Screen texts of the send sheet window: when it was sent, the counts, the ignored rows and the columns."""
from datetime import datetime, timedelta

from sheet_sync.sheet import Ignored

NO_COLUMN = "Nenhuma"  # the CT-e column is optional
_SEPARATOR = " · "
_MAX_LINES = 10  # ignored line numbers shown per reason

_COUNT_LABELS = {
    "new": ("nova", "novas"),
    "updated": ("atualizada", "atualizadas"),
    "ignored": ("linha ignorada", "linhas ignoradas"),
}


def sent_label(when: datetime, now: datetime) -> str:
    """"hoje às 14:20", "ontem às 09:05", "12/11 às 09:05" or "12/11/2025 às 09:05", in now's timezone."""
    local = when.astimezone(now.tzinfo)
    hour = local.strftime("%H:%M")
    if local.date() == now.date():
        return f"hoje às {hour}"
    if local.date() == now.date() - timedelta(days=1):
        return f"ontem às {hour}"
    day = local.strftime("%d/%m") if local.year == now.year else local.strftime("%d/%m/%Y")
    return f"{day} às {hour}"


def count_label(kind: str, count: int) -> str:
    singular, plural = _COUNT_LABELS[kind]
    return singular if count == 1 else plural


def _number(n: int) -> str:
    return f"{n:,}".replace(",", ".")


def _join(items: list[str]) -> str:
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " e " + items[-1]


def ignored_lines(ignored: list[Ignored]) -> list[str]:
    """One line per reason, in the order the reasons first show up in the sheet."""
    by_reason: dict[str, list[int]] = {}
    for row in sorted(ignored, key=lambda i: i.line):
        by_reason.setdefault(row.reason, []).append(row.line)

    texts = []
    for reason, lines in by_reason.items():
        shown = [_number(n) for n in lines[:_MAX_LINES]]
        hidden = len(lines) - len(shown)
        numbers = ", ".join(shown) + f" e mais {hidden}" if hidden else _join(shown)
        noun = "linha" if len(lines) == 1 else "linhas"
        texts.append(f"{reason[0].upper()}{reason[1:]} ({noun} {numbers}).")
    return texts


def column_options(headers: list[tuple[str, str]]) -> list[str]:
    """"D · Nota fiscal" for each column, or just "D" when the header cell is empty."""
    return [f"{letter}{_SEPARATOR}{title}" if title else letter for letter, title in headers]


def letter_of(option: str) -> str | None:
    if not option or option == NO_COLUMN:
        return None
    return option.split(_SEPARATOR, 1)[0]


def title_of(option: str) -> str:
    """The header title of an option, "" for a column with an empty header cell (or no column)."""
    parts = option.split(_SEPARATOR, 1)
    return parts[1] if len(parts) == 2 else ""
