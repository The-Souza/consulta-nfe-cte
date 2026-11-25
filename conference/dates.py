"""Delivery dates typed during the review: DD/MM/AAAA, with shorter forms for speed."""

import re
from datetime import date

_SLASHED = re.compile(r"(\d{1,2})/(\d{1,2})(?:/(\d{2}|\d{4}))?")
_DIGITS = re.compile(r"\d{4}|\d{6}|\d{8}")
_MAX_DIGITS = 8
_MAX_LENGTH = len("DD/MM/AAAA")


class DateError(ValueError):
    """The text is not a valid delivery date; the message is shown next to the field."""


def _parts(text: str) -> tuple[int, int, str | None]:
    if match := _SLASHED.fullmatch(text):
        day, month, year = match.groups()
        return int(day), int(month), year
    if _DIGITS.fullmatch(text):
        return int(text[:2]), int(text[2:4]), text[4:] or None
    raise DateError("Data inválida")


def _build(year: int, month: int, day: int) -> date:
    try:
        return date(year, month, day)
    except ValueError:
        raise DateError("Data inválida") from None


def parse_date(text: str, today: date) -> date | None:
    """The date in `text`, or None when it is empty.

    Without a year, the current one is used; if that gives a date after `today` (in January, typing
    20/12), the year before. A delivery cannot happen after today, so a future date with a year is refused.
    """
    text = text.strip()
    if not text:
        return None
    day, month, year = _parts(text)
    if year is None:
        result = _build(today.year, month, day)
        return result if result <= today else _build(today.year - 1, month, day)
    result = _build(2000 + int(year) if len(year) == 2 else int(year), month, day)
    if result > today:
        raise DateError("Data no futuro")
    return result


def mask(text: str) -> str:
    """Adds the slashes while digits are typed (`1411` → `14/11`). Slashes typed by hand are kept."""
    if "/" in text:
        return re.sub(r"[^\d/]", "", text)[:_MAX_LENGTH]
    digits = re.sub(r"\D", "", text)[:_MAX_DIGITS]
    return "/".join(part for part in (digits[:2], digits[2:4], digits[4:]) if part)


def short(value: date) -> str:
    return f"{value:%d/%m}"


def full(value: date) -> str:
    return f"{value:%d/%m/%Y}"
