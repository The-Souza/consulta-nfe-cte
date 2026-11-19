from functools import lru_cache
from typing import Callable

import customtkinter as ctk
from PIL import Image, ImageDraw

from ui import theme
from utils.search_results import CHIPS
from utils.status import Tone

_DOT_TONES = {
    "ok": Tone.OK,
    "no_cte": Tone.WARNING,
    "not_found": Tone.ERROR,
    "no_image": Tone.INFO,
    "connection": Tone.CONNECTION,
}
_DOT_SIZE = 8


@lru_cache
def _dot(color: str) -> ctk.CTkImage:
    """Filled circle in a status color (Lucide's `circle` is only an outline)."""
    big = _DOT_SIZE * 4  # drawn larger and scaled down by CTkImage for smooth edges
    image = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    ImageDraw.Draw(image).ellipse((0, 0, big - 1, big - 1), fill=color)
    return ctk.CTkImage(light_image=image, dark_image=image, size=(_DOT_SIZE, _DOT_SIZE))


class FilterChips(ctk.CTkFrame):
    """'Filtrar:' followed by one pill per filter with its count. A chip with 0 is dimmed and can't be
    picked; the active one is inverted. set_active(None) leaves none pressed (e.g. a CT-e filter)."""

    def __init__(self, parent, on_pick: Callable[[str], None]):
        super().__init__(parent, fg_color=theme.TRANSPARENT)
        self._on_pick = on_pick
        self._labels = {key: label for key, label, _ in CHIPS}
        self._counts = {key: 0 for key in self._labels}
        self._active: str | None = "all"

        ctk.CTkLabel(
            self, text="Filtrar:", text_color=theme.TEXT_MUTED, font=theme.font(theme.FONT_SIZE_SM),
        ).pack(side="left", padx=(0, theme.SPACE_SM))
        self._buttons: dict[str, ctk.CTkButton] = {}
        for key in self._labels:
            tone = _DOT_TONES.get(key)
            button = ctk.CTkButton(
                self, text="", width=0, height=30, corner_radius=15, border_width=1,
                font=theme.font(theme.FONT_SIZE_BODY), compound="left",
                image=_dot(theme.STATUS[tone.value][0]) if tone else None,
                command=lambda k=key: self._pick(k),
            )
            button.pack(side="left", padx=(0, theme.SPACE_SM))
            self._buttons[key] = button
        self._render()

    def set_counts(self, counts: dict[str, int]) -> None:
        self._counts = counts
        self._render()

    def set_active(self, key: str | None) -> None:
        self._active = key
        self._render()

    def _pick(self, key: str) -> None:
        if self._counts.get(key, 0) or key == "all":
            self._on_pick(key)

    def _render(self) -> None:
        for key, button in self._buttons.items():
            count = self._counts.get(key, 0)
            button.configure(text=f"{self._labels[key]}   {count}")
            if key == self._active:
                button.configure(
                    state="normal", fg_color=theme.TEXT, hover_color=theme.TEXT, text_color=theme.BG,
                    border_color=theme.TEXT,
                )
            elif count == 0 and key != "all":
                button.configure(
                    state="disabled", fg_color=theme.TRANSPARENT, text_color_disabled=theme.TEXT_MUTED,
                    border_color=theme.BORDER,
                )
            else:
                button.configure(
                    state="normal", fg_color=theme.SURFACE, hover_color=theme.SURFACE_2, text_color=theme.TEXT,
                    border_color=theme.BORDER_INPUT,
                )
