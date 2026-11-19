"""Driver and delivery date lookup from the Supabase entregas table (read-only)."""
import logging
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Callable, Iterable, Literal

import requests

from config import SUPABASE_ANON_KEY, SUPABASE_URL

logger = logging.getLogger(__name__)

TIMEOUT = (5, 15)
BATCH_SIZE = 200
CTE_BATCH_SIZE = 50  # a CT-e has up to ~12 invoices: 50 CT-es stay under PAGE_SIZE rows
PAGE_SIZE = 1000  # PostgREST default max rows per response
_COLUMNS = "nfe,cte,motorista,data_entrega"
_FRACTION = re.compile(r"\.(\d+)")


@dataclass(frozen=True)
class Delivery:
    driver: str
    date: date | None


@dataclass(frozen=True)
class DriverLookup:
    deliveries: dict[int, Delivery]
    updated_at: datetime | None
    state: Literal["off", "ok", "failed"]


def get_drivers(nfes: Iterable[int], session: requests.Session | None = None) -> DriverLookup:
    """Reads driver and delivery date for each NF-e. Never raises: a failure is logged and returns state "failed"."""
    if not (SUPABASE_URL and SUPABASE_ANON_KEY):
        return DriverLookup({}, None, "off")
    wanted = sorted(set(nfes))
    if not wanted:
        return DriverLookup({}, None, "ok")

    def read(http: requests.Session) -> tuple[dict[int, Delivery], datetime | None]:
        if len(wanted) > 1 and wanted[-1] - wanted[0] == len(wanted) - 1:
            rows = _read_range(http, wanted[0], wanted[-1])
        else:
            rows = _read_batches(http, "nfe", wanted)
        return {int(row["nfe"]): _delivery(row) for row in rows}, _read_updated_at(http)

    return _lookup(read, session)


def get_drivers_by_cte(ctes: Iterable[int], session: requests.Session | None = None) -> DriverLookup:
    """Driver and delivery date keyed by CT-e, for invoices of a load issued with a single XML.
    Every row of a CT-e has the same driver and date, so the first one is kept."""
    if not (SUPABASE_URL and SUPABASE_ANON_KEY):
        return DriverLookup({}, None, "off")
    wanted = sorted(set(ctes))
    if not wanted:
        return DriverLookup({}, None, "ok")

    def read(http: requests.Session) -> tuple[dict[int, Delivery], datetime | None]:
        deliveries: dict[int, Delivery] = {}
        for row in _read_batches(http, "cte", wanted, CTE_BATCH_SIZE):
            deliveries.setdefault(int(row["cte"]), _delivery(row))
        return deliveries, None

    return _lookup(read, session)


def sheet_label(updated_at: datetime | None, now: datetime) -> str:
    if updated_at is None:
        return ""
    day = updated_at.date()
    if day == now.date():
        when = "hoje"
    elif day == now.date() - timedelta(days=1):
        when = "ontem"
    elif day.year == now.year:
        when = day.strftime("%d/%m")
    else:
        when = day.strftime("%d/%m/%Y")
    return f"planilha de {when}, {updated_at:%H:%M}"


def _lookup(
    read: Callable[[requests.Session], tuple[dict[int, Delivery], datetime | None]],
    session: requests.Session | None,
) -> DriverLookup:
    http = session or requests.Session()
    try:
        deliveries, updated_at = read(http)
    except (requests.RequestException, ValueError, KeyError, TypeError):
        logger.warning("Could not read drivers from Supabase", exc_info=True)
        return DriverLookup({}, None, "failed")
    finally:
        if session is None:
            http.close()
    return DriverLookup(deliveries, updated_at, "ok")


def _get(http: requests.Session, params: list[tuple[str, str | int]]) -> list[dict]:
    resp = http.get(
        f"{SUPABASE_URL}/rest/v1/entregas",
        params=params,
        headers={"apikey": SUPABASE_ANON_KEY},
        timeout=TIMEOUT,
    )
    resp.raise_for_status()
    data = resp.json()
    if not isinstance(data, list):
        raise ValueError(f"Unexpected Supabase payload: {type(data).__name__}")
    return data


def _read_range(http: requests.Session, first: int, last: int) -> list[dict]:
    rows: list[dict] = []
    offset = 0
    while True:
        page = _get(http, [
            ("select", _COLUMNS),
            ("nfe", f"gte.{first}"),
            ("nfe", f"lte.{last}"),
            ("order", "nfe"),
            ("limit", PAGE_SIZE),
            ("offset", offset),
        ])
        rows.extend(page)
        if len(page) < PAGE_SIZE:
            return rows
        offset += PAGE_SIZE


def _read_batches(http: requests.Session, column: str, values: list[int], size: int = BATCH_SIZE) -> list[dict]:
    rows: list[dict] = []
    for start in range(0, len(values), size):
        batch = ",".join(map(str, values[start:start + size]))
        rows.extend(_get(http, [("select", _COLUMNS), (column, f"in.({batch})")]))
    return rows


def _read_updated_at(http: requests.Session) -> datetime | None:
    rows = _get(http, [("select", "atualizado_em"), ("order", "atualizado_em.desc"), ("limit", 1)])
    return _parse_timestamp(rows[0]["atualizado_em"]) if rows else None


def _parse_timestamp(text: str) -> datetime:
    # Python 3.10 only accepts 3 or 6 fractional digits; Postgres trims trailing zeros
    text = _FRACTION.sub(lambda m: "." + m.group(1)[:6].ljust(6, "0"), text.replace("Z", "+00:00"), count=1)
    return datetime.fromisoformat(text).astimezone()


def _delivery(row: dict) -> Delivery:
    day = row["data_entrega"]
    return Delivery(str(row["motorista"]), date.fromisoformat(day) if day else None)
