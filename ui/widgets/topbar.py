from typing import Callable

import customtkinter as ctk

from ui import theme
from ui.icons import get_icon

_HEIGHT = 52
_BUTTON_HEIGHT = 32


def _ghost_button(parent, text: str, icon: str, command: Callable) -> ctk.CTkButton:
    return ctk.CTkButton(
        parent, text=text, image=get_icon(icon, 14, theme.TEXT), compound="left",
        width=0, height=_BUTTON_HEIGHT, corner_radius=theme.RADIUS_INPUT,
        fg_color="transparent", hover_color=theme.SURFACE_2,
        border_width=1, border_color=theme.BORDER_INPUT,
        text_color=theme.TEXT, font=theme.font(theme.FONT_SIZE_BODY),
        command=command,
    )


def make_topbar(parent, title: str, user_name: str, on_logout: Callable, on_back: Callable | None = None) -> None:
    topbar = ctk.CTkFrame(parent, height=_HEIGHT, corner_radius=0, fg_color=theme.TOPBAR)
    topbar.pack(fill="x")
    topbar.pack_propagate(False)
    ctk.CTkFrame(parent, height=1, corner_radius=0, fg_color=theme.TOPBAR_BORDER).pack(fill="x")

    if on_back:
        _ghost_button(topbar, "Voltar", "chevron-left", on_back).pack(
            side="left", padx=(theme.SPACE_LG, 0)
        )

    ctk.CTkLabel(
        topbar, text=title, text_color=theme.TEXT, font=theme.font(theme.FONT_SIZE_MD, "bold"),
    ).pack(side="left", padx=theme.SPACE_LG)

    _ghost_button(topbar, "Sair", "log-out", on_logout).pack(side="right", padx=theme.SPACE_LG)

    if user_name:
        ctk.CTkLabel(
            topbar, text=user_name, text_color=theme.TEXT_MUTED, font=theme.font(theme.FONT_SIZE_BODY),
        ).pack(side="right")
