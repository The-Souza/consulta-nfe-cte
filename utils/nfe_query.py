"""Parses the search field: one NF-e (`4516661`), a range (`4516661-4516680`) or a list separated by
commas, spaces, `;` or line breaks (as pasted from Excel), ranges included."""

import re
from dataclasses import dataclass, field

MAX_INVOICES = 200  # a real query stays around 60 NF-es; more is almost always a typo

_SEPARATORS = re.compile(r"[\s,;]+")
_SPACED_HYPHEN = re.compile(r"\s*-\s*")
_NUMBER = re.compile(r"^\d+$")
_RANGE = re.compile(r"^(\d+)-(\d+)$")


@dataclass(frozen=True)
class ParsedQuery:
    invoices: list[int] = field(default_factory=list)
    label: str = ""
    valid: bool = False


def parse_query(text: str) -> ParsedQuery:
    text = _SPACED_HYPHEN.sub("-", text)  # "4516661 - 4516680" is a range, not three tokens
    tokens = [t for t in _SEPARATORS.split(text.strip()) if t]
    if not tokens:
        return ParsedQuery()

    spans: list[tuple[int, int]] = []
    for token in tokens:
        if _NUMBER.match(token):
            spans.append((int(token), int(token)))
            continue
        match = _RANGE.match(token)
        if not match or int(match[1]) > int(match[2]):
            return ParsedQuery(label="Formato não reconhecido")
        spans.append((int(match[1]), int(match[2])))

    too_many = ParsedQuery(label=f"Máximo de {MAX_INVOICES} NF-es por consulta")
    unique: dict[int, None] = {}
    for start, end in spans:
        # Each span is checked before it is expanded, so a typo like 1-999999999 never builds a huge list.
        if end - start + 1 > MAX_INVOICES:
            return too_many
        unique.update(dict.fromkeys(range(start, end + 1)))
        if len(unique) > MAX_INVOICES:
            return too_many

    invoices = list(unique)
    if len(invoices) == 1:
        label = "1 NF-e"
    elif len(tokens) == 1:
        label = f"Faixa · {len(invoices)} NF-es"
    else:
        label = f"Lista · {len(invoices)} NF-es"
    return ParsedQuery(invoices=invoices, label=label, valid=True)
