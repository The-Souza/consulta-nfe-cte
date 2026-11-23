"""Reads and writes the entregas table through the Supabase REST API, with the secret key."""
import logging
from dataclasses import dataclass
from datetime import date, datetime, timezone

import requests

from sheet_sync.diff import Changes, Stored
from sheet_sync.settings import SyncConfig
from sheet_sync.sheet import Entry

logger = logging.getLogger(__name__)

TIMEOUT = (5, 30)
PAGE_SIZE = 1000  # PostgREST answers at most 1000 rows per request
BATCH_SIZE = 1000
_TABLE = "/rest/v1/entregas"
_COLUMNS = "id,nfe,cte,motorista,data_entrega"


class SupabaseError(Exception):
    """A failed read. The message is shown on screen and never carries the key."""


@dataclass(frozen=True)
class SendResult:
    written: int
    error: str | None = None


def _headers(config: SyncConfig, prefer: str | None = None) -> dict[str, str]:
    # A secret key (sb_secret_...) isn't a JWT: it goes only in apikey, like the app's publishable key
    headers = {"apikey": config.secret_key}
    if prefer:
        headers["Prefer"] = prefer
    return headers


def _message(error: Exception, action: str) -> str:
    """Screen text for a failure. The response body may echo request data, so it only goes to the log."""
    if isinstance(error, requests.HTTPError) and error.response is not None:
        status = error.response.status_code
        logger.debug("Supabase answered %s: %s", status, error.response.text)
        if status in (401, 403):
            return "A chave não tem permissão para gravar. Confira a SUPABASE_SECRET_KEY em enviar_planilha.env."
        return f"O Supabase recusou {action} (HTTP {status})."
    if isinstance(error, (requests.ConnectionError, requests.Timeout)):
        return "Sem conexão com o Supabase."
    return "O Supabase devolveu uma resposta inesperada."


def _stored(row: dict) -> Stored:
    day = row["data_entrega"]
    return Stored(id=row["id"], nfe=row["nfe"], cte=row["cte"], driver=row["motorista"],
                  date=date.fromisoformat(day) if day else None)


def fetch_stored(config: SyncConfig, session: requests.Session | None = None) -> list[Stored]:
    """Every row of the table, a page at a time. Raises SupabaseError with the screen message."""
    session = session or requests.Session()
    stored: list[Stored] = []
    offset = 0
    try:
        while True:
            response = session.get(
                config.url + _TABLE, headers=_headers(config), timeout=TIMEOUT,
                params={"select": _COLUMNS, "order": "id", "limit": PAGE_SIZE, "offset": offset},
            )
            response.raise_for_status()
            page = [_stored(row) for row in response.json()]
            stored += page
            if len(page) < PAGE_SIZE:
                return stored
            offset += PAGE_SIZE
    except (requests.RequestException, ValueError, KeyError, TypeError) as error:
        logger.warning("Could not read the entregas table", exc_info=True)
        raise SupabaseError(_message(error, "a leitura")) from error


def _payload(entry: Entry, updated_at: str) -> dict:
    return {
        "nfe": entry.nfe,
        "cte": entry.cte,
        "motorista": entry.driver,
        "data_entrega": entry.date.isoformat() if entry.date else None,
        "atualizado_em": updated_at,
    }


def _batches(rows: list[dict]) -> list[list[dict]]:
    return [rows[i:i + BATCH_SIZE] for i in range(0, len(rows), BATCH_SIZE)]


def send(changes: Changes, config: SyncConfig, session: requests.Session | None = None,
         now: datetime | None = None) -> SendResult:
    """Inserts the new rows and updates the changed ones by id, in batches. Stops at the first failure: the
    rows already written come back as unchanged on the next send, which finishes the job."""
    session = session or requests.Session()
    updated_at = (now or datetime.now(timezone.utc)).isoformat()
    new = [_payload(e, updated_at) for e in changes.new]
    # The primary key is a full unique index, so PostgREST can merge on it (the nfe/cte ones are partial)
    updated = [{"id": table_id, **_payload(e, updated_at)} for table_id, e in changes.updated]
    # Every row of a request must have the same keys, so new and updated rows never share one
    requests_to_send = [({}, "return=minimal", batch) for batch in _batches(new)] + [
        ({"on_conflict": "id"}, "resolution=merge-duplicates,return=minimal", batch) for batch in _batches(updated)
    ]

    written = 0
    for params, prefer, batch in requests_to_send:
        try:
            response = session.post(config.url + _TABLE, params=params, json=batch,
                                    headers=_headers(config, prefer), timeout=TIMEOUT)
            response.raise_for_status()
        except requests.RequestException as error:
            logger.warning("Could not write to the entregas table", exc_info=True)
            return SendResult(written=written, error=_message(error, "o envio"))
        written += len(batch)
    return SendResult(written=written)
