from enum import Enum


class Tone(str, Enum):
    """Visual tone of a status; values are keys of `ui.theme.STATUS`."""

    OK = "ok"
    WARNING = "warning"
    ERROR = "error"
    CONNECTION = "connection"
    INFO = "info"
    NEUTRAL = "neutral"


SEARCH_OK = "OK"
SEARCH_NO_CTE = "Sem CT-e"
SEARCH_NOT_FOUND = "Não cadastrada"
CONNECTION_FAILED = "Falha de conexão"

_SEARCH_TONES = {
    SEARCH_OK: Tone.OK,
    SEARCH_NO_CTE: Tone.WARNING,
    SEARCH_NOT_FOUND: Tone.ERROR,
    CONNECTION_FAILED: Tone.CONNECTION,
}

_RENAME_STATUS = {
    "ok": ("Renomeada", Tone.OK),
    "duplicata": ("Duplicata", Tone.WARNING),
    "nao_encontrada": ("Não lida", Tone.ERROR),
    "erro": ("Erro", Tone.ERROR),
}


def search_tone(label: str) -> Tone:
    """Tone of a search result; any unknown label is an error message from the API."""
    return _SEARCH_TONES.get(label, Tone.ERROR)


def rename_status(key: str) -> tuple[str, Tone]:
    """Label and tone of a rename result key produced by the rename worker."""
    return _RENAME_STATUS.get(key, _RENAME_STATUS["erro"])
