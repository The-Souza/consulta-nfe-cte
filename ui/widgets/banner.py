import tkinter
from typing import Callable, Sequence

import customtkinter as ctk

from ui import theme
from ui.icons import get_icon
from utils.status import Tone


class Banner:
    """Full-width strip in a status tone: optional icon, text and action buttons (the first one is the
    main action). Starts hidden.

    It lives in a slot that stays packed, so showing it again keeps its place among its siblings.
    `bg` is the parent's color: the empty slot is 1 px tall and must not show."""

    def __init__(self, parent, bg: str):
        self._slot = tkinter.Frame(parent, bg=bg, height=0, bd=0, highlightthickness=0)
        self._bar = ctk.CTkFrame(self._slot, corner_radius=0, height=44)
        self._icon = ctk.CTkLabel(self._bar, text="", width=16)
        self._text = ctk.CTkLabel(
            self._bar, text="", anchor="w", justify="left", font=theme.font(theme.FONT_SIZE_BODY),
        )
        self._actions = ctk.CTkFrame(self._bar, fg_color=theme.TRANSPARENT)
        # Wrap long messages to the space left by the icon and the buttons instead of cutting them.
        self._bar.bind("<Configure>", lambda _event: self._wrap_text())

    def _wrap_text(self) -> None:
        # winfo_* sizes are physical pixels; CTk scales wraplength and paddings by the Windows zoom.
        scaling = ctk.ScalingTracker.get_widget_scaling(self._bar)
        used = (2 * theme.SPACE_MD + theme.SPACE_LG) * scaling
        if self._icon.winfo_manager():
            used += self._icon.winfo_reqwidth()
        if self._actions.winfo_manager():
            used += self._actions.winfo_reqwidth() + theme.SPACE_MD * scaling
        wraplength = max(int((self._bar.winfo_width() - used) / scaling), 120)
        if self._text.cget("wraplength") != wraplength:
            self._text.configure(wraplength=wraplength)

    def pack(self, **options) -> None:
        self._slot.pack(**options)

    def show(
        self, tone: Tone, text: str, actions: Sequence[tuple[str, Callable]] = (), icon: str | None = None,
    ) -> None:
        text_color, bg_color = theme.STATUS[tone.value]
        self._bar.configure(fg_color=bg_color)

        self._icon.pack_forget()
        if icon:
            self._icon.configure(image=get_icon(icon, 16, text_color))
            self._icon.pack(side="left", padx=(theme.SPACE_LG, 0))
        self._text.configure(text=text, text_color=text_color)
        self._text.pack_forget()  # re-packed after the actions so they keep the right edge
        self._actions.pack_forget()

        for button in self._actions.winfo_children():
            button.destroy()
        for i, (label, command) in enumerate(actions):
            main = i == 0
            ctk.CTkButton(
                self._actions, text=label, command=command, height=30, width=0,
                corner_radius=theme.RADIUS_INPUT - 2,
                font=theme.font(theme.FONT_SIZE_BODY, "bold" if main else "normal"),
                fg_color=text_color if main else theme.TRANSPARENT,
                hover_color=text_color if main else theme.SURFACE_2,
                text_color=theme.BG if main else text_color,
                border_width=0 if main else 1, border_color=text_color,
            ).pack(side="left", padx=(theme.SPACE_SM, 0))
        if actions:  # an empty CTkFrame would still ask for 200 px, so it's only packed with buttons
            self._actions.pack(side="right", padx=(0, theme.SPACE_MD))
        self._text.pack(side="left", fill="x", expand=True, padx=theme.SPACE_MD, pady=theme.SPACE_SM)

        self._bar.pack(fill="x")
        self._wrap_text()

    def hide(self) -> None:
        self._bar.pack_forget()
        # Tk keeps an emptied frame at its last size; setting a height makes it shrink back.
        self._slot.configure(height=1)
        self._slot.configure(height=0)

    @property
    def visible(self) -> bool:
        return self._bar.winfo_manager() != ""

    @property
    def text(self) -> str:
        return self._text.cget("text")

    def set_text(self, text: str) -> None:
        """Change only the message of a banner already shown (show() would rebuild its buttons)."""
        if text != self.text:
            self._text.configure(text=text)
