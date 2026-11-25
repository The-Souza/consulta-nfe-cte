"""File names shortened for the photo list."""

import os

ELLIPSIS = "…"
# Long enough for the copy counter WhatsApp adds before the extension: "(1).jpeg".
_MIN_TAIL = 8


def shorten_middle(name: str, max_len: int = 33) -> str:
    """Cuts the middle of a long name, keeping its start and its end with the extension.

    `WhatsApp Image 2026-11-14 at 18.42.07 (1).jpeg` → `WhatsApp Image 2026-11-1…(1).jpeg`
    """
    if len(name) <= max_len:
        return name
    extension = os.path.splitext(name)[1]
    tail = min(max(len(extension), _MIN_TAIL), max_len - 2)  # at least one character of the start
    head = max_len - tail - len(ELLIPSIS)
    return name[:head] + ELLIPSIS + name[-tail:]
