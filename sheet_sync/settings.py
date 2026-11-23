import io
import json
import logging
import sys
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import dotenv_values

logger = logging.getLogger(__name__)

# Next to enviar-planilha.exe, or at the repo root when running from source. Never the app's .env.
_BASE = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent.parent
CONFIG_FILE = _BASE / "enviar_planilha.env"
PREFS_FILE = _BASE / "enviar_planilha.json"

_REQUIRED = ("SUPABASE_URL", "SUPABASE_SECRET_KEY")
_PUBLISHABLE_PREFIX = "sb_publishable_"


@dataclass(frozen=True)
class SyncConfig:
    url: str
    secret_key: str = field(repr=False)  # never in logs, tracebacks or on screen
    sheet_path: str = ""

    @property
    def missing(self) -> list[str]:
        values = {"SUPABASE_URL": self.url, "SUPABASE_SECRET_KEY": self.secret_key}
        return [name for name in _REQUIRED if not values[name]]

    @property
    def read_only_key(self) -> bool:
        """The app's publishable key can only read: catch it before trying to write."""
        return self.secret_key.startswith(_PUBLISHABLE_PREFIX)


def load_config(path: Path = CONFIG_FILE) -> SyncConfig:
    values = {}
    if path.exists():
        # utf-8-sig: a BOM left by Windows tools would otherwise stick to the first name.
        # dotenv_values doesn't export to os.environ: the key stays inside this object.
        values = dotenv_values(stream=io.StringIO(path.read_text(encoding="utf-8-sig")))
    return SyncConfig(
        url=(values.get("SUPABASE_URL") or "").rstrip("/"),
        secret_key=values.get("SUPABASE_SECRET_KEY") or "",
        sheet_path=values.get("PLANILHA_PATH") or "",
    )


@dataclass(frozen=True)
class Prefs:
    path: str = ""
    columns: dict[str, str | None] = field(default_factory=dict)  # "nfe", "cte", "driver", "date" -> letter
    # Header title of each chosen column: a column inserted in the sheet moves the titles, not the letters
    titles: dict[str, str] = field(default_factory=dict)
    auto_send: bool = False


def _read_json(path: Path) -> dict:
    """The file as a dict; missing, unreadable or non-object content counts as empty."""
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        logger.warning("Could not read %s", path, exc_info=True)
        return {}
    return data if isinstance(data, dict) else {}


def load_prefs(path: Path = PREFS_FILE) -> Prefs:
    data = _read_json(path)
    columns = data.get("columns")
    valid_columns = isinstance(columns, dict) and all(
        isinstance(k, str) and (v is None or isinstance(v, str)) for k, v in columns.items()
    )
    titles = data.get("titles")
    valid_titles = isinstance(titles, dict) and all(
        isinstance(k, str) and isinstance(v, str) for k, v in titles.items()
    )
    return Prefs(
        path=data["path"] if isinstance(data.get("path"), str) else "",
        columns=dict(columns) if valid_columns else {},
        titles=dict(titles) if valid_titles else {},
        auto_send=data["auto_send"] if isinstance(data.get("auto_send"), bool) else False,
    )


def save_prefs(prefs: Prefs, path: Path = PREFS_FILE) -> None:
    # Only our keys change: anything else in the file is kept
    data = _read_json(path)
    data.update(path=prefs.path, columns=prefs.columns, titles=prefs.titles, auto_send=prefs.auto_send)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
