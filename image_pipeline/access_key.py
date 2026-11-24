"""NF-e access key (chave de acesso): 44 digits printed in the stub's QR code."""

import re

KEY_LENGTH = 44
NFE_MODEL = "55"

_KEY_PATTERN = re.compile(r"(?<!\d)\d{44}(?!\d)", re.ASCII)


def _check_digit(body: str) -> int:
    # Modulo 11 with weights 2..9 repeating from the rightmost digit.
    total = sum(int(digit) * (2 + i % 8) for i, digit in enumerate(reversed(body)))
    remainder = total % 11
    return 0 if remainder < 2 else 11 - remainder


def is_valid_key(key: str) -> bool:
    if len(key) != KEY_LENGTH or not key.isascii() or not key.isdigit():
        return False
    if key[20:22] != NFE_MODEL:
        return False
    return _check_digit(key[:43]) == int(key[43])


def find_key(text: str) -> str | None:
    """First valid NF-e key in a QR payload, bare or inside a URL."""
    for match in _KEY_PATTERN.finditer(text):
        if is_valid_key(match.group()):
            return match.group()
    return None


def nfe_from_key(key: str) -> int:
    return int(key[25:34])
