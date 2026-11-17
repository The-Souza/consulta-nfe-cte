"""Lucide icons (white PNGs in assets/icons/) tinted at load time, plus the optional local logo."""

import functools
import logging
import sys
from pathlib import Path

import customtkinter as ctk
from PIL import Image

from ui import theme

logger = logging.getLogger(__name__)

# PyInstaller extracts bundled data under sys._MEIPASS; from source, assets/ sits at the repo root.
_BASE_DIR = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
ICONS_DIR = _BASE_DIR / "assets" / "icons"


def tint(image: Image.Image, color: str) -> Image.Image:
    """Return a solid `color` image that keeps the alpha channel of `image`."""
    rgba = image.convert("RGBA")
    tinted = Image.new("RGBA", rgba.size, color)
    tinted.putalpha(rgba.getchannel("A"))
    return tinted


@functools.lru_cache(maxsize=None)
def get_icon(name: str, size: int, color: str = theme.TEXT) -> ctk.CTkImage:
    path = ICONS_DIR / f"{name}.png"
    if not path.exists():
        raise FileNotFoundError(f"Icon '{name}' not found at {path}")
    with Image.open(path) as image:
        tinted = tint(image, color)
    return ctk.CTkImage(light_image=tinted, dark_image=tinted, size=(size, size))


def load_logo(path: Path, size: int) -> Image.Image | None:
    """Load the local logo (.ico or any image) as RGBA at `size` px, or None if missing/unreadable."""
    if not path.exists():
        return None
    try:
        with Image.open(path) as image:
            if image.format == "ICO":
                image = image.ico.getimage(max(image.ico.sizes()))
            logo = image.convert("RGBA")
    except (OSError, ValueError):
        logger.warning("Could not load logo from %s", path, exc_info=True)
        return None
    return logo.resize((size, size), Image.Resampling.LANCZOS)
