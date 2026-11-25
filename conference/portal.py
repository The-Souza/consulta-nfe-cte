"""What the portal already has for an invoice: its delivery date and whether it still takes an image.

Only the two read calls of the upload are used, so the review never writes anything. The result is shown
during the review only: the send step reads the details again right before each upload, so a date the
company registers in between is never overwritten (R15 of Etapa 6).
"""

import logging
import threading
from collections.abc import Callable
from datetime import date, datetime, timedelta, timezone

import api
from conference.photo import SystemInfo

logger = logging.getLogger(__name__)

APPROVED = "APROVADO"
# Brazil has no daylight saving time since 2019. A delivery stored as a UTC instant (the app itself sends
# 12:00Z) is read in Brazilian time, so an instant like 02:00Z still counts as the day before.
_BRAZIL = timezone(timedelta(hours=-3))


def _delivery(details: dict) -> date | None:
    raw = (details.get("documentoIndustria") or {}).get("dataEntrega")
    if not raw:
        return None
    try:
        if "/" in raw:
            return datetime.strptime(raw, "%d/%m/%Y").date()
        moment = datetime.fromisoformat(raw)
    except (TypeError, ValueError):
        logger.warning("Unreadable delivery date from the portal: %r", raw)
        return None
    return moment.astimezone(_BRAZIL).date() if moment.tzinfo else moment.date()


def check(
    session,
    nfe: int,
    relogin: Callable[[], object],
    stop: threading.Event | None = None,
    client=api,
    now: Callable[[], datetime] = datetime.now,
) -> SystemInfo:
    """Looks the invoice up in the portal. Cancelled and SessionLost reach the caller, which stops."""

    def call(fn: Callable):
        return api.call_with_relogin(fn, relogin)

    try:
        oid, status = call(lambda: client.get_invoice_for_upload(session, str(nfe), stop=stop))
        if oid is None:
            return SystemInfo("not_found", None, now())
        if status == APPROVED:
            return SystemInfo("approved", None, now())
        details = call(lambda: client.get_invoice_details(session, oid, stop=stop))
    except api.ConnectionFailed:
        return SystemInfo("unavailable", None, now())
    return SystemInfo("found", _delivery(details), now())
