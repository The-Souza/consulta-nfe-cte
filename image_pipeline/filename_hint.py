"""Date hint taken from the names WhatsApp and Windows give to photos."""

import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import PureWindowsPath
from typing import Literal

Source = Literal["whatsapp", "screenshot"]

_PATTERNS: list[tuple[Source, re.Pattern[str]]] = [
    (
        "whatsapp",
        re.compile(
            r"WhatsApp Image (\d{4})-(\d{2})-(\d{2}) at (\d{2})\.(\d{2})\.(\d{2})(?: \(\d+\))?\.jpe?g",
            re.IGNORECASE | re.ASCII,
        ),
    ),
    (
        "screenshot",
        re.compile(r"Captura de tela (\d{4})-(\d{2})-(\d{2}) (\d{2})(\d{2})(\d{2})\.png", re.IGNORECASE | re.ASCII),
    ),
]


@dataclass(frozen=True)
class FilenameHint:
    source: Source
    taken_at: datetime

    def label(self) -> str:
        when = f"{self.taken_at:%d/%m} às {self.taken_at:%H:%M}"
        if self.source == "whatsapp":
            return f"Foto recebida no WhatsApp em {when}"
        return f"Captura de tela de {when}"


def hint_from_filename(path: str) -> FilenameHint | None:
    # PureWindowsPath splits on both "\" and "/", whatever the OS running the tests.
    name = PureWindowsPath(path).name
    for source, pattern in _PATTERNS:
        match = pattern.fullmatch(name)
        if match:
            try:
                return FilenameHint(source, datetime(*map(int, match.groups())))
            except ValueError:
                return None
    return None
