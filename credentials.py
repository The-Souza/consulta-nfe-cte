import json
import sys
import keyring
from pathlib import Path

from config import APP_NAME

_base            = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).parent
_CONFIG          = _base / "config.json"
_KEYRING_SERVICE = APP_NAME


def salvar(email: str, senha: str) -> None:
    _CONFIG.write_text(json.dumps({"email": email}), encoding="utf-8")
    keyring.set_password(_KEYRING_SERVICE, email, senha)


def carregar() -> tuple[str, str]:
    email, senha = "", ""
    if _CONFIG.exists():
        try:
            email = json.loads(_CONFIG.read_text(encoding="utf-8")).get("email", "")
        except Exception:
            pass
    if email:
        try:
            senha = keyring.get_password(_KEYRING_SERVICE, email) or ""
        except Exception:
            pass
    return email, senha
