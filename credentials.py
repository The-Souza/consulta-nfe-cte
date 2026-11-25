import logging

import keyring

import local_config
from config import APP_NAME

logger = logging.getLogger(__name__)

_CONFIG          = local_config.CONFIG_FILE
_KEYRING_SERVICE = APP_NAME


def save(email: str, password: str) -> None:
    # Only the email changes: config.json may hold other settings
    data = local_config.read(_CONFIG)
    data["email"] = email
    local_config.write(data, _CONFIG)
    keyring.set_password(_KEYRING_SERVICE, email, password)


def load() -> tuple[str, str]:
    email, password = local_config.read(_CONFIG).get("email", ""), ""
    if email:
        try:
            password = keyring.get_password(_KEYRING_SERVICE, email) or ""
        except Exception:
            pass
    return email, password


def remember_by_default(email: str, password: str) -> bool:
    """Initial state of 'remember password': on for first use or a saved password, off when only
    the email is saved (the user already chose not to keep the password)."""
    return bool(password) or not email


def forget_password(email: str) -> None:
    """Keep `email` for the next login but remove the stored passwords (of `email` and of the
    previously saved email). Never raises: failures are only logged, because this runs right after
    a successful login."""
    data = local_config.read(_CONFIG)
    saved_email = data.get("email", "")

    for address in {saved_email, email} - {""}:
        try:
            keyring.delete_password(_KEYRING_SERVICE, address)
        except keyring.errors.PasswordDeleteError:
            pass  # nothing stored for this email
        except Exception:
            # Backends may raise raw OS errors (e.g. access denied), not only KeyringError.
            logger.warning("Could not remove saved password from the keyring", exc_info=True)

    data["email"] = email
    try:
        local_config.write(data, _CONFIG)
    except OSError:
        logger.warning("Could not update %s", _CONFIG, exc_info=True)
