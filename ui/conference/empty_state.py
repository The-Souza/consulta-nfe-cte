from typing import Callable

import customtkinter as ctk

from ui import theme
from ui.icons import get_icon

_TEXT = (
    "Jogue as fotos do WhatsApp e as capturas de tela na pasta Canhotos\\entrada, de vários dias misturados. "
    "As datas você define na conferência. O app lê o número da NF-e de cada foto (.jpg, .jpeg ou .png) "
    "assim que a pasta é carregada."
)
_WIDTH = 420


class EmptyState(ctk.CTkFrame):
    """No work folder yet (R1): what to do and the "Selecionar pasta" button."""

    def __init__(self, parent, on_pick: Callable[[], None]):
        super().__init__(
            parent, fg_color=theme.SURFACE, border_color=theme.BORDER_INPUT, border_width=1,
            corner_radius=theme.RADIUS_CARD,
        )
        box = ctk.CTkFrame(self, fg_color=theme.TRANSPARENT)
        box.place(relx=0.5, rely=0.5, anchor="center")
        ctk.CTkLabel(
            box, text="", image=get_icon("folder", 30, theme.TEXT_MUTED), width=64, height=64,
            corner_radius=16, fg_color=theme.SURFACE_2,
        ).pack()
        ctk.CTkLabel(
            box, text="Nenhuma imagem carregada", text_color=theme.TEXT, font=theme.font(17, "bold"),
        ).pack(pady=(14, 0))
        ctk.CTkLabel(
            box, text=_TEXT, text_color=theme.TEXT_MUTED, wraplength=_WIDTH, justify="center",
            font=theme.font(theme.FONT_SIZE_INPUT),
        ).pack(pady=(14, 0))
        # Packed only when there is something to warn about (see set_notice)
        self._notice = ctk.CTkLabel(
            box, text="", text_color=theme.STATUS["warning"][0], wraplength=_WIDTH, justify="center",
            font=theme.font(theme.FONT_SIZE_BODY),
        )
        self._button = ctk.CTkButton(
            box, text="Selecionar pasta", image=get_icon("folder", 16, theme.TEXT_ON_PRIMARY), compound="left",
            width=0, height=40, corner_radius=theme.RADIUS_INPUT, fg_color=theme.PRIMARY,
            hover_color=theme.PRIMARY_HOVER, text_color=theme.TEXT_ON_PRIMARY,
            font=theme.font(theme.FONT_SIZE_INPUT, "bold"), command=on_pick,
        )
        self._button.pack(pady=(14, 0))

    def set_notice(self, text: str | None) -> None:
        """A warning above the button, e.g. the saved folder no longer exists."""
        if text:
            self._notice.configure(text=text)
            self._notice.pack(pady=(14, 0), before=self._button)
        else:
            self._notice.pack_forget()
