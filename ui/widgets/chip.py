import customtkinter as ctk

from ui import theme
from utils.status import Tone


def make_chip(parent, tone: Tone) -> ctk.CTkLabel:
    text_color, bg_color = theme.STATUS[tone.value]
    frame = ctk.CTkFrame(parent, fg_color=bg_color, corner_radius=theme.RADIUS_CHIP)
    frame.pack(side="left", padx=(0, theme.SPACE_SM))
    lbl = ctk.CTkLabel(frame, text="", text_color=text_color, font=theme.font(theme.FONT_SIZE_XS), height=18)
    lbl.pack(padx=theme.SPACE_MD, pady=3)
    return lbl
