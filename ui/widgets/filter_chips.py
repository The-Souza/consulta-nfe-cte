from collections.abc import Sequence
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

_STATE_STYLES = {
    "active": dict(
        state="normal", fg_color=theme.TEXT, hover_color=theme.TEXT, text_color=theme.BG, border_color=theme.TEXT,
    ),
    "empty": dict(
        state="disabled", fg_color=theme.TRANSPARENT, text_color_disabled=theme.TEXT_MUTED, border_color=theme.BORDER,
    ),
    "normal": dict(
        state="normal", fg_color=theme.SURFACE, hover_color=theme.SURFACE_2, text_color=theme.TEXT,
        border_color=theme.BORDER_INPUT,
    ),
}


@lru_cache
def _dot(color: str) -> ctk.CTkImage:
    """Filled circle in a status color (Lucide's `circle` is only an outline)."""
    big = _DOT_SIZE * 4  # drawn larger and scaled down by CTkImage for smooth edges
    image = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    ImageDraw.Draw(image).ellipse((0, 0, big - 1, big - 1), fill=color)
    return ctk.CTkImage(light_image=image, dark_image=image, size=(_DOT_SIZE, _DOT_SIZE))


class FilterChips(ctk.CTkFrame):
    """'Filtrar:' followed by one pill per filter with its count. A chip with 0 is dimmed and can't be
    picked; the active one is inverted. set_active(None) leaves none pressed (e.g. a CT-e filter).

    The first chip is the "all" one, never dimmed. The defaults are the search chips."""

    def __init__(self, parent, on_pick: Callable[[str], None],
                 chips: Sequence[tuple[str, str]] = tuple((key, label) for key, label, _ in CHIPS),
                 dots: dict[str, Tone] = _DOT_TONES, title: str | None = "Filtrar:"):
        super().__init__(parent, fg_color=theme.TRANSPARENT)
        self._on_pick = on_pick
        self._labels = dict(chips)
        self._all = chips[0][0]
        self._counts = {key: 0 for key in self._labels}
        self._active: str | None = self._all
        self._shown: dict[str, tuple[str | None, str | None]] = {}  # key -> (text, state) on screen
        self._pinned: set[str] = set()  # chips with a fixed width (set on a state change)

        if title:
            ctk.CTkLabel(
                self, text=title, text_color=theme.TEXT_MUTED, font=theme.font(theme.FONT_SIZE_SM),
            ).pack(side="left", padx=(0, theme.SPACE_SM))
        self._buttons: dict[str, ctk.CTkButton] = {}
        for key in self._labels:
            tone = dots.get(key)
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
        if self._counts.get(key, 0) or key == self._all:
            self._on_pick(key)

    def _render(self) -> None:
        # Each CTkButton.configure redraws the whole button, which flickers when the counts change on
        # every search row: only touch what changed (the text, or the colors when the state changes).
        for key, button in self._buttons.items():
            count = self._counts.get(key, 0)
            text = f"{self._labels[key]}   {count}"
            if key == self._active:
                state = "active"
            elif count == 0 and key != self._all:
                state = "empty"
            else:
                state = "normal"

            shown_text, shown_state = self._shown.get(key, (None, None))
            # The colors go first: when the count changes too (a chip leaving 0 during a search), the new
            # text is set on a pinned chip below, which resizes it without a jump.
            if state != shown_state:
                # While redrawing new colors, an auto-sized CTkButton shrinks to its minimum for a moment
                # and every chip to its right jumps left and back. Pin the width it already has.
                if shown_state is not None:
                    button.configure(width=self._width_on_screen(button), **_STATE_STYLES[state])
                    self._pinned.add(key)
                else:
                    button.configure(**_STATE_STYLES[state])
            if text != shown_text:
                if key in self._pinned:  # the count changed: let a pinned chip size itself again
                    self._pinned.discard(key)
                    button.configure(text=text, width=0)
                else:
                    button.configure(text=text)  # text only: CTkButton doesn't redraw for it
            self._shown[key] = (text, state)

    @staticmethod
    def _width_on_screen(button: ctk.CTkButton) -> int:
        """Width on screen, in the logical px that CTkButton(width=) takes."""
        return round(button.winfo_width() / ctk.ScalingTracker.get_widget_scaling(button))
