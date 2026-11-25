"""Delivery dates typed during the review: DD/MM/AAAA, with shorter forms for speed."""

import re
from datetime import date, timedelta

# Stubs are sent every week, so a pending one is at most a month or two old. Six months leaves plenty of
# room and still catches a mistyped year ("14/12/25" for 2026), which would reach the portal for good.
MAX_AGE = timedelta(days=183)

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


def _check_range(value: date, today: date) -> date:
    if value > today:
        raise DateError("Data no futuro")
    if today - value > MAX_AGE:
        raise DateError("Data muito antiga")
    return value


def parse_date(text: str, today: date) -> date | None:
    """The date in `text`, or None when it is empty.

    Without a year, the current one is used; if that gives a date after `today` (in January, typing
    20/12), the year before. A delivery cannot happen after today, nor more than six months before it.
    """
    text = text.strip()
    if not text:
        return None
    day, month, year = _parts(text)
    if year is None:
        this_year = _build(today.year, month, day)
        if this_year <= today:
            return _check_range(this_year, today)
        last_year = _build(today.year - 1, month, day)
        if today - last_year > MAX_AGE:
            raise DateError("Data no futuro")  # most likely a future date typed by mistake
        return last_year
    return _check_range(_build(2000 + int(year) if len(year) == 2 else int(year), month, day), today)


def mask(text: str) -> str:
    """Adds the slashes while digits are typed (`1411` → `14/11`), on every keystroke.

    Slashes are rebuilt from the digits while the day and the month have two digits each, which covers the
    slashes the mask itself added. A one-digit day or month (`4/1/2026`) means they were typed by hand, so
    they are kept as they are.
    """
    text = re.sub(r"[^\d/]", "", text)
    if any(len(part) != 2 for part in text.split("/")[:-1]):
        return text[:_MAX_LENGTH]
    digits = text.replace("/", "")[:_MAX_DIGITS]
    return "/".join(part for part in (digits[:2], digits[2:4], digits[4:]) if part)


def short(value: date) -> str:
    return f"{value:%d/%m}"


def full(value: date) -> str:
    return f"{value:%d/%m/%Y}"
