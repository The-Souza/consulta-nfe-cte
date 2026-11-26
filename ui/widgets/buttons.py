from typing import Callable

import customtkinter as ctk

from ui import theme
from ui.icons import get_icon
from utils.status import Tone

_RESTORE_KEYS = ("text", "image", "fg_color", "hover_color", "text_color", "command")


def show_cancel(button: ctk.CTkButton, command: Callable) -> dict:
    """Turn the button of a running task into 'Cancelar'. Returns the options to give back to restore_button."""
    previous = {key: button.cget(key) for key in _RESTORE_KEYS}
    text_color, bg_color = theme.STATUS[Tone.ERROR.value]
    button.configure(
        text="Cancelar", image=get_icon("square", 14, text_color), compound="left",
        fg_color=bg_color, hover_color=theme.SURFACE_2, text_color=text_color, command=command,
    )
    return previous


def restore_button(button: ctk.CTkButton, previous: dict) -> None:
    button.configure(**previous)


def link_button(parent, text: str, command: Callable, icon: str = "chevron-right") -> ctk.CTkButton:
    """A borderless text button, as the links between the new and the old upload flow."""
    return ctk.CTkButton(
        parent, text=text, image=get_icon(icon, 14, theme.TEXT_LABEL), compound="left", width=0, height=28,
        corner_radius=theme.RADIUS_INPUT, fg_color=theme.TRANSPARENT, hover_color=theme.SURFACE_2,
        text_color=theme.TEXT_LABEL, font=theme.font(theme.FONT_SIZE_BODY), command=command,
    )


def set_enabled(button: ctk.CTkButton, enabled: bool, icon: str, color: str = theme.TEXT_ON_PRIMARY,
                size: int = 16) -> None:
    """CTkButton dims the text of a disabled button but leaves its image as it was: dim the icon too."""
    button.configure(
        state="normal" if enabled else "disabled", text_color_disabled=theme.TEXT_MUTED,
        image=get_icon(icon, size, color if enabled else theme.TEXT_MUTED),
    )
