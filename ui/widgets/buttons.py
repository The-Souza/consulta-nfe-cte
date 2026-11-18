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
