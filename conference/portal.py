"""What the portal already has for an invoice: its delivery date and whether it still takes an image.

Only the two read calls of the upload are used, so the review never writes anything. The result is shown
during the review only: the send step reads the details again right before each upload, so a date the
company registers in between is never overwritten (R15 of Etapa 6).
"""

import logging
import threading
from collections.abc import Callable
from datetime import date, datetime, timedelta, timezone

import requests

import api
from conference.photo import SystemInfo

logger = logging.getLogger(__name__)

PENDING = "PENDENTE"  # the only status that takes an image, as in the send step
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
    """Looks the invoice up in the portal. Cancelled and SessionLost reach the caller, which stops.

    A connection failure or any other request failure (a 404 or 400 that is not about the session, a
    response cut mid-transfer, a redirect loop) means the portal could not answer now: "unavailable", so
    the screen lets the date be typed and asks again later.
    """

    def call(fn: Callable):
        return api.call_with_relogin(fn, relogin)

    try:
        oid, status = call(lambda: client.get_invoice_for_upload(session, str(nfe), stop=stop))
        if oid is None:
            return SystemInfo("not_found", None, now())
        if status == APPROVED:
            return SystemInfo("approved", None, now(), status)
        if status != PENDING:
            return SystemInfo("other", None, now(), status)
        details = call(lambda: client.get_invoice_details(session, oid, stop=stop))
    except (api.ConnectionFailed, requests.RequestException):
        return SystemInfo("unavailable", None, now())
    return SystemInfo("found", _delivery(details), now(), status)
