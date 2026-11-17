import json
import logging
import sys
import keyring
from pathlib import Path

from config import APP_NAME

logger = logging.getLogger(__name__)

_base            = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).parent
_CONFIG          = _base / "config.json"
_KEYRING_SERVICE = APP_NAME


def save(email: str, password: str) -> None:
    _CONFIG.write_text(json.dumps({"email": email}), encoding="utf-8")
    keyring.set_password(_KEYRING_SERVICE, email, password)


def load() -> tuple[str, str]:
    email, password = "", ""
    if _CONFIG.exists():
        try:
            email = json.loads(_CONFIG.read_text(encoding="utf-8")).get("email", "")
        except Exception:
            pass
    if email:
        try:
            password = keyring.get_password(_KEYRING_SERVICE, email) or ""
        except Exception:
            pass
    return email, password


def _read_config() -> dict | None:
    if not _CONFIG.exists():
        return None
    try:
        data = json.loads(_CONFIG.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        logger.warning("Could not read %s while clearing credentials", _CONFIG, exc_info=True)
        return None
    return data if isinstance(data, dict) else None


def clear(email: str = "") -> None:
    """Forget the saved login and the password of `email`. Never raises: failures are only logged,
    because this runs right after a successful login."""
    data = _read_config()
    saved_email = data.get("email", "") if data else ""

    for address in {saved_email, email} - {""}:
        try:
            keyring.delete_password(_KEYRING_SERVICE, address)
        except keyring.errors.PasswordDeleteError:
            pass  # nothing stored for this email
        except Exception:
            # Backends may raise raw OS errors (e.g. access denied), not only KeyringError.
            logger.warning("Could not remove saved password from the keyring", exc_info=True)

    if data and "email" in data:
        del data["email"]
        try:
            _CONFIG.write_text(json.dumps(data), encoding="utf-8")
        except OSError:
            logger.warning("Could not update %s while clearing credentials", _CONFIG, exc_info=True)
