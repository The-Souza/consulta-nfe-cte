from typing import Callable

import customtkinter as ctk

from conference.batch import Summary
from conference.labels import send_label, summary_parts
from ui import theme
from ui.widgets.buttons import link_button, set_enabled

# D1: the new upload comes in 2.0.0-alpha.7; until then the review ends here and the old flow sends.
_SEND_LATER = "O envio chega na próxima versão"


class BottomBar(ctk.CTkFrame):
    """The old flow link on the left; the ready/pending summary and "Enviar N canhotos" on the right (R21)."""

    def __init__(self, parent, on_legacy: Callable[[], None]):
        super().__init__(parent, fg_color=theme.TRANSPARENT)
        link_button(self, "Usar o fluxo antigo", on_legacy).pack(side="left")

        self._send = ctk.CTkButton(
            self, text=send_label(0), compound="left", width=0, height=38, corner_radius=theme.RADIUS_INPUT,
            fg_color=theme.SURFACE_2, font=theme.font(theme.FONT_SIZE_INPUT, "bold"),
        )
        set_enabled(self._send, False, "upload")
        self._send.pack(side="right")
        ctk.CTkLabel(
            self, text=_SEND_LATER, text_color=theme.TEXT_MUTED, font=theme.font(theme.FONT_SIZE_SM),
        ).pack(side="right", padx=(0, theme.SPACE_MD))
        self._rest = ctk.CTkLabel(self, text="", text_color=theme.TEXT_MUTED, font=theme.font(theme.FONT_SIZE_BODY))
        self._rest.pack(side="right", padx=(0, theme.SPACE_MD))
        self._ready = ctk.CTkLabel(
            self, text="", text_color=theme.STATUS["ok"][0], font=theme.font(theme.FONT_SIZE_BODY, "bold"),
        )
        self._ready.pack(side="right")

    def update_summary(self, summary: Summary) -> None:
        ready, rest = summary_parts(summary)
        self._ready.configure(text=ready)
        self._rest.configure(text=rest)
        self._send.configure(text=send_label(summary.ready))
