import customtkinter as ctk

from ui import theme
from utils.status import Tone


def make_progress(parent) -> tuple[ctk.CTkLabel, ctk.CTkProgressBar]:
    label = ctk.CTkLabel(parent, text="", anchor="w", text_color=theme.TEXT)
    label.pack(fill="x", pady=(4, 2))
    progress_bar = ctk.CTkProgressBar(parent)
    progress_bar.pack(fill="x", pady=(0, 8))
    progress_bar.set(0)
    return label, progress_bar


def set_message(label: ctk.CTkLabel, text: str, tone: Tone | None = None) -> None:
    """Progress/feedback text; a tone colors it like the matching status badge."""
    color = theme.STATUS[tone.value][0] if tone else theme.TEXT
    label.configure(text=text, text_color=color)
