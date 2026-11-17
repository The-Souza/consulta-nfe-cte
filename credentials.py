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


def clear() -> None:
    """Forget the saved login: remove the password from the keyring and the email from config.json."""
    if not _CONFIG.exists():
        return
    try:
        data = json.loads(_CONFIG.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        logger.warning("Could not read %s while clearing credentials", _CONFIG, exc_info=True)
        return
    email = data.pop("email", "")
    if email:
        try:
            keyring.delete_password(_KEYRING_SERVICE, email)
        except keyring.errors.PasswordDeleteError:
            pass  # nothing stored for this email
    _CONFIG.write_text(json.dumps(data), encoding="utf-8")
