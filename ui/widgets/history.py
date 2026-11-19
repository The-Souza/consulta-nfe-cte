from typing import Callable

import customtkinter as ctk

from ui import theme
from ui.icons import get_icon
from ui.widgets.scrollbar import hide_frame_scrollbar_when_idle


class HistoryPanel:
    def __init__(self, parent, on_restore: Callable[[dict], None]):
        self._history: list[dict] = []
        self._visible = False
        self._on_restore = on_restore

        self._btn_toggle = ctk.CTkButton(
            parent, text="Histórico (0)", image=get_icon("chevron-right", 16, theme.TEXT_MUTED), compound="left",
            fg_color=theme.TRANSPARENT, hover_color=theme.SURFACE_2, text_color=theme.TEXT_LABEL,
            font=theme.font(theme.FONT_SIZE_BODY), anchor="w", height=28, corner_radius=theme.RADIUS_INPUT,
            command=self._toggle,
        )
        self._btn_toggle.pack(fill="x", pady=(10, 0))
        self._scroll = ctk.CTkScrollableFrame(
            parent, height=88, fg_color=theme.SURFACE, corner_radius=theme.RADIUS_INPUT,
            scrollbar_button_color=theme.SCROLLBAR_BUTTON, scrollbar_button_hover_color=theme.SCROLLBAR_BUTTON_HOVER,
        )
        hide_frame_scrollbar_when_idle(self._scroll)

    def add(self, entry: dict) -> None:
        self._history.insert(0, entry)
        self._update_btn()
        self._rebuild()

    def refresh(self) -> None:
        """Redraw the labels after an entry was updated in place."""
        self._rebuild()

    def _toggle(self) -> None:
        self._visible = not self._visible
        self._update_btn()
        if self._visible:
            self._scroll.pack(fill="x", pady=(2, 0))
        else:
            self._scroll.pack_forget()

    def _rebuild(self) -> None:
        for w in self._scroll.winfo_children():
            w.destroy()
        for entry in self._history:
            ctk.CTkButton(
                self._scroll,
                text=entry["label"],
                fg_color=theme.TRANSPARENT, hover_color=theme.SURFACE_2, text_color=theme.TEXT,
                font=theme.font(theme.FONT_SIZE_BODY), anchor="w", height=28, corner_radius=theme.RADIUS_INPUT,
                command=lambda e=entry: self._on_restore(e),
            ).pack(fill="x", pady=1)

    def _update_btn(self) -> None:
        icon = "chevron-down" if self._visible else "chevron-right"
        self._btn_toggle.configure(
            text=f"Histórico ({len(self._history)})", image=get_icon(icon, 16, theme.TEXT_MUTED),
        )
