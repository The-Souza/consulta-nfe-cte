"""Window size that fits the screen. Kept free of Tk so it can be tested.

Sizes are logical pixels (what CustomTkinter's geometry() takes and multiplies by the Windows zoom);
the work area and the position are physical pixels (what Windows reports and what geometry() uses
for +x+y).
"""

import ctypes
import logging
import sys
from dataclasses import dataclass

logger = logging.getLogger(__name__)

TITLEBAR = 32  # window title bar, not part of the geometry height (logical px)


@dataclass(frozen=True)
class WorkArea:
    """Screen area not covered by the taskbar, in physical px."""
    x: int
    y: int
    width: int
    height: int


@dataclass(frozen=True)
class WindowFit:
    width: int
    height: int
    min_width: int
    min_height: int
    x: int
    y: int


def work_area(window) -> WorkArea:
    """Physical work area of the main screen. Tk's winfo_screenwidth/height can't be used on Windows:
    with the zoom on they come back in another unit (1536×864 on a 1920×1080 screen at 125%)."""
    if sys.platform == "win32":
        class _Rect(ctypes.Structure):
            _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                        ("right", ctypes.c_long), ("bottom", ctypes.c_long)]

        rect = _Rect()
        spi_getworkarea = 0x0030
        try:
            if ctypes.windll.user32.SystemParametersInfoW(spi_getworkarea, 0, ctypes.byref(rect), 0):
                return WorkArea(rect.left, rect.top, rect.right - rect.left, rect.bottom - rect.top)
        except (AttributeError, OSError):
            logger.debug("Could not read the work area", exc_info=True)
    return WorkArea(0, 0, window.winfo_screenwidth(), window.winfo_screenheight())


def fit_window(
    *, width: int, height: int, min_width: int, min_height: int, area: WorkArea, scaling: float,
) -> WindowFit:
    """The wanted size, reduced to what fits the work area, centered on it. The minimum never exceeds it."""
    fit_width = min(width, int(area.width / scaling))
    fit_height = min(height, int(area.height / scaling) - TITLEBAR)

    x = area.x + max(0, round((area.width - fit_width * scaling) / 2))
    y = area.y + max(0, round((area.height - (fit_height + TITLEBAR) * scaling) / 2))
    return WindowFit(
        width=fit_width, height=fit_height,
        min_width=min(min_width, fit_width), min_height=min(min_height, fit_height),
        x=x, y=y,
    )
