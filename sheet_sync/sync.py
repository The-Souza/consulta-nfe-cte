"""One full send: read the sheet, read the table, compare and write what changed."""
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import requests

from sheet_sync.diff import compare
from sheet_sync.settings import SyncConfig
from sheet_sync.sheet import Columns, Ignored, SheetError, read_entries, read_headers
from sheet_sync.supabase import SupabaseError, fetch_stored, send

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SyncResult:
    finished_at: datetime  # UTC
    new: int = 0
    updated: int = 0
    unchanged: int = 0
    written: int = 0  # rows that reached the table; less than new + updated when the send failed halfway
    ignored: list[Ignored] = field(default_factory=list)
    error: str | None = None  # screen text; never carries the key
    preview: bool = False  # counted only, nothing was written
    columns_changed: bool = False  # a chosen column no longer has the title it was chosen by


_FIELD_LABELS = {"nfe": "NF-e", "driver": "Motorista", "date": "Data de entrega", "cte": "CT-e"}


def _changed_columns(headers: list[tuple[str, str]], columns: Columns, titles: dict[str, str]) -> list[str]:
    """Fields whose column letter now holds another header title, e.g. after a column was inserted in Excel:
    sending by letter would write the wrong data for everyone."""
    current = dict(headers)
    return [label for name, label in _FIELD_LABELS.items()
            if getattr(columns, name) is not None and current.get(getattr(columns, name)) != titles.get(name)]


def config_error(config: SyncConfig) -> str | None:
    """What blocks a send in enviar_planilha.env, as screen text; the window shows it before any click."""
    if config.missing:
        return f"Falta preencher em enviar_planilha.env: {', '.join(config.missing)}."
    if config.read_only_key:
        return ("A chave em enviar_planilha.env é a publishable do app, que só lê. "
                "Use a SUPABASE_SECRET_KEY do projeto.")
    return None


def sync(path: Path | str, columns: Columns, config: SyncConfig, session: requests.Session | None = None,
         now: datetime | None = None, preview: bool = False, titles: dict[str, str] | None = None) -> SyncResult:
    """Never raises for the expected failures: they come back in `error`, with whatever was done until then.
    `preview` reads the sheet and the table and counts the changes, without writing anything.
    `titles` are the header titles the columns were chosen by; if one changed, nothing is read or sent."""
    now = now or datetime.now(timezone.utc)
    path = Path(path)

    error = config_error(config)
    if error:
        return SyncResult(finished_at=now, error=error)

    try:
        if titles is not None:
            changed = _changed_columns(read_headers(path), columns, titles)
            if changed:
                return SyncResult(finished_at=now, columns_changed=True, error=(
                    f"As colunas da planilha mudaram ({', '.join(changed)}). Confira as colunas e tente de novo."
                ))
        entries, ignored = read_entries(path, columns)
    except FileNotFoundError:
        return SyncResult(finished_at=now, error=f"Planilha não encontrada: {path.name}")
    except SheetError as sheet_error:
        return SyncResult(finished_at=now, error=str(sheet_error))
    except OSError:
        logger.warning("Could not read %s", path, exc_info=True)
        return SyncResult(finished_at=now, error=f"Não foi possível ler a planilha {path.name}.")

    session = session or requests.Session()
    try:
        stored = fetch_stored(config, session)
    except SupabaseError as supabase_error:
        return SyncResult(finished_at=now, ignored=ignored, error=str(supabase_error))

    changes = compare(entries, stored)
    if preview:
        return SyncResult(finished_at=now, new=len(changes.new), updated=len(changes.updated),
                          unchanged=changes.unchanged, ignored=ignored, preview=True)
    sent = send(changes, config, session, now)
    return SyncResult(
        finished_at=now, new=len(changes.new), updated=len(changes.updated), unchanged=changes.unchanged,
        written=sent.written, ignored=ignored, error=sent.error,
    )
