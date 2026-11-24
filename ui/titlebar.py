"""Dark, theme-colored title bar on Windows 11 via DWM. A no-op anywhere it is not supported."""

import ctypes
import logging
import re
import sys

from ui import theme

logger = logging.getLogger(__name__)

DWMWA_USE_IMMERSIVE_DARK_MODE = 20
DWMWA_WINDOW_CORNER_PREFERENCE = 33
DWMWA_BORDER_COLOR = 34
DWMWA_CAPTION_COLOR = 35
DWMWCP_ROUND = 2

_HEX_COLOR = re.compile(r"#([0-9a-fA-F]{2})([0-9a-fA-F]{2})([0-9a-fA-F]{2})")


def hex_to_colorref(color: str) -> int:
    """Convert '#RRGGBB' to a Win32 COLORREF (0x00BBGGRR)."""
    match = _HEX_COLOR.fullmatch(color)
    if not match:
        raise ValueError(f"Expected a '#RRGGBB' color, got {color!r}")
    red, green, blue = (int(part, 16) for part in match.groups())
    return (blue << 16) | (green << 8) | red


def _set_attributes(window, attributes: tuple[tuple[int, int], ...]) -> None:
    if sys.platform != "win32":
        return
    try:
        hwnd = ctypes.windll.user32.GetParent(window.winfo_id())
        for attribute, value in attributes:
            data = ctypes.c_uint(value)
            result = ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd, attribute, ctypes.byref(data), ctypes.sizeof(data)
            )
            if result != 0:
                logger.debug("DwmSetWindowAttribute(%s) returned 0x%08X", attribute, result & 0xFFFFFFFF)
    except (AttributeError, OSError):
        logger.debug("Could not set window attributes", exc_info=True)


def apply_titlebar(window, color: str = theme.TITLEBAR) -> None:
    """Paint the native title bar of a Tk window. Older Windows versions ignore the attributes."""
    _set_attributes(window, ((DWMWA_USE_IMMERSIVE_DARK_MODE, 1), (DWMWA_CAPTION_COLOR, hex_to_colorref(color))))


def round_corners(window, border: str = theme.BORDER_INPUT) -> None:
    """Rounded corners and a thin border drawn by Windows 11 on a borderless window (e.g. a dropdown list).
    Older Windows versions ignore it and keep square corners."""
    _set_attributes(window, ((DWMWA_WINDOW_CORNER_PREFERENCE, DWMWCP_ROUND),
                             (DWMWA_BORDER_COLOR, hex_to_colorref(border))))
