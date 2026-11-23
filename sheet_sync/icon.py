"""The uploader's icon: a green square with the upload arrow, like the login fallback logo. Drawn at run time,
because *.ico files stay out of the repo (they may carry a company brand)."""
from pathlib import Path

from PIL import Image, ImageDraw

from ui import theme
from ui.icons import ICONS_DIR, tint

_SIZES = [(16, 16), (32, 32), (48, 48), (64, 64), (256, 256)]


def icon_image(size: int = 256) -> Image.Image:
    icon = Image.new("RGBA", (size, size))
    ImageDraw.Draw(icon).rounded_rectangle((0, 0, size - 1, size - 1), radius=size // 4.5, fill=theme.PRIMARY)
    glyph_size = round(size * 0.56)
    with Image.open(ICONS_DIR / "upload.png") as arrow:
        glyph = tint(arrow, theme.TEXT_ON_PRIMARY).resize((glyph_size, glyph_size), Image.Resampling.LANCZOS)
    offset = (size - glyph_size) // 2
    icon.alpha_composite(glyph, (offset, offset))
    return icon


def save_icon(path: Path | str) -> None:
    """An .ico with the sizes Windows uses for the title bar, the taskbar and the .exe file."""
    icon_image().save(path, sizes=_SIZES)


if __name__ == "__main__":  # build_enviar.ps1: python -m sheet_sync.icon <path>
    import sys

    save_icon(sys.argv[1])
