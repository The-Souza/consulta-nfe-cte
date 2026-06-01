import customtkinter as ctk


def make_chip(parent, text_color: str, bg_color: str) -> ctk.CTkLabel:
    frame = ctk.CTkFrame(parent, fg_color=bg_color, corner_radius=20)
    frame.pack(side="left", padx=(0, 8))
    lbl = ctk.CTkLabel(frame, text="", text_color=text_color, font=ctk.CTkFont(size=11))
    lbl.pack(padx=12, pady=3)
    return lbl
