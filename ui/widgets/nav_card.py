from typing import Callable

import customtkinter as ctk

from ui import theme
from ui.icons import get_icon

_ICON_BOX = 44
_PADDING = 18


class NavCard(ctk.CTkFrame):
    """Clickable card with a tinted icon, title, description and a chevron."""

    def __init__(self, parent, icon: str, tone: str, title: str, description: str, command: Callable):
        super().__init__(
            parent, fg_color=theme.SURFACE, border_color=theme.BORDER, border_width=1,
            corner_radius=theme.RADIUS_CARD,
        )
        self._command = command
        text_color, bg_color = theme.STATUS[tone]

        ctk.CTkLabel(
            self, text="", width=_ICON_BOX, height=_ICON_BOX, corner_radius=theme.RADIUS_ICON,
            fg_color=bg_color, image=get_icon(icon, 22, text_color),
        ).pack(side="left", padx=(_PADDING, theme.SPACE_LG), pady=_PADDING)

        ctk.CTkLabel(
            self, text="", image=get_icon("chevron-right", 18, theme.TEXT_MUTED),
        ).pack(side="right", padx=(theme.SPACE_LG, _PADDING))

        texts = ctk.CTkFrame(self, fg_color="transparent")
        texts.pack(side="left", fill="x", expand=True)
        ctk.CTkLabel(
            texts, text=title, text_color=theme.TEXT, font=theme.font(theme.FONT_SIZE_MD, "bold"),
            anchor="w", height=20,
        ).pack(fill="x")
        ctk.CTkLabel(
            texts, text=description, text_color=theme.TEXT_MUTED, font=theme.font(theme.FONT_SIZE_BODY),
            anchor="w", height=18,
        ).pack(fill="x", pady=(theme.SPACE_XS, 0))

        self._bind_tree(self)

    def _bind_tree(self, widget) -> None:
        widget.bind("<Button-1>", self._on_click)
        widget.bind("<Enter>", self._on_enter)
        widget.bind("<Leave>", self._on_leave)
        widget.configure(cursor="hand2")
        for child in widget.winfo_children():
            self._bind_tree(child)

    def _on_click(self, _event=None) -> None:
        # The screen changes under the pointer and Tk may never send <Leave>.
        self.configure(fg_color=theme.SURFACE)
        self._command()

    def _on_enter(self, _event=None) -> None:
        self.configure(fg_color=theme.SURFACE_2)

    def _on_leave(self, _event=None) -> None:
        # Moving between child widgets fires <Leave>; only reset when the pointer really left the card.
        hovered = self.winfo_containing(*self.winfo_pointerxy())
        # Compare with a trailing dot: '.!navcard2' must not count as inside '.!navcard'.
        inside = hovered is not None and (str(hovered) == str(self) or str(hovered).startswith(f"{self}."))
        if not inside:
            self.configure(fg_color=theme.SURFACE)
