"""Texts of the review screen that depend on the photos (the UI only draws them)."""

from conference.batch import Summary
from conference.dates import short

_MAX_DATES = 4


def _plural(count: int, one: str, many: str) -> str:
    return f"{count} {one if count == 1 else many}"


def _dates(summary: Summary) -> str:
    shown = ", ".join(short(d) for d in summary.ready_dates[:_MAX_DATES])
    hidden = len(summary.ready_dates) - _MAX_DATES
    return f"{shown} e mais {hidden}" if hidden > 0 else shown


def summary_parts(summary: Summary) -> tuple[str, str]:
    """The bottom bar text in two parts: the ready count (drawn in green) and the rest."""
    if not summary.ready and not summary.pending:
        return "", ""
    if summary.ready:
        ready, rest = _plural(summary.ready, "pronta", "prontas"), f" em {_dates(summary)}"
    else:
        ready, rest = "Nenhuma pronta", ""
    if summary.pending:
        fica = "fica" if summary.pending == 1 else "ficam"
        rest += f" · {_plural(summary.pending, 'pendente', 'pendentes')} {fica} na lista"
    return ready, rest


def send_label(ready: int) -> str:
    return f"Enviar {_plural(ready, 'canhoto', 'canhotos')}" if ready else "Enviar canhotos"
