from datetime import date
from typing import Callable

import customtkinter as ctk

from conference.dates import short
from conference.labels import selection_label
from ui import theme
from ui.icons import get_icon

_MAX_DATES = 9  # the 1–9 shortcuts of the panel use the same dates
_TEXT, _LINE, _OUTLINE = theme.BANNER["info"]
_BG = theme.STATUS["info"][1]
_NO_DATES = "nenhuma data na conferência ainda"


class BatchBar(ctk.CTkFrame):
    """"N selecionadas · aplicar data: [14/11] [15/11] · Marcar conferidas" (R8), shown with a selection."""

    def __init__(self, parent, on_apply: Callable[[date], None], on_confirm: Callable[[], None],
                 on_clear: Callable[[], None]):
        super().__init__(parent, fg_color=_BG, border_color=_LINE, border_width=1, corner_radius=theme.RADIUS_INPUT)
        self._on_apply = on_apply
        self._dates: list[date] | None = None
        self._label = ctk.CTkLabel(self, text="", text_color=_TEXT, font=theme.font(theme.FONT_SIZE_SM, "bold"))
        self._label.pack(side="left", padx=(10, theme.SPACE_XS), pady=6)
        self._date_row = ctk.CTkFrame(self, fg_color=theme.TRANSPARENT)
        self._date_row.pack(side="left")
        self._confirm = self._button("Marcar conferidas", on_confirm)
        self._confirm.pack(side="left", padx=(theme.SPACE_XS, 0))
        ctk.CTkButton(
            self, text="", image=get_icon("x", 14, _TEXT), width=26, height=26, corner_radius=6,
            fg_color=theme.TRANSPARENT, hover_color=_OUTLINE, command=on_clear,
        ).pack(side="right", padx=(0, 6))

    def _button(self, text: str, command: Callable[[], None], mono: bool = False) -> ctk.CTkButton:
        return ctk.CTkButton(
            self._date_row if mono else self, text=text, width=0, height=26, corner_radius=6, border_width=1,
            fg_color=_BG, hover_color=_OUTLINE, border_color=_OUTLINE,
            text_color=_TEXT, font=theme.font(theme.FONT_SIZE_SM, mono=mono), command=command,
        )

    def update_selection(self, count: int, dates: list[date]) -> None:
        self._label.configure(text=f"{selection_label(count)}  ·  aplicar data:")
        dates = dates[:_MAX_DATES]
        if dates == self._dates:
            return  # rebuilding the buttons on every click would flicker
        self._dates = dates
        for child in self._date_row.winfo_children():
            child.destroy()
        if not dates:
            ctk.CTkLabel(
                self._date_row, text=_NO_DATES, text_color=_TEXT, font=theme.font(theme.FONT_SIZE_SM),
            ).pack(side="left", padx=theme.SPACE_XS)
        for value in dates:
            self._button(short(value), lambda v=value: self._on_apply(v), mono=True).pack(
                side="left", padx=(theme.SPACE_XS, 0),
            )
