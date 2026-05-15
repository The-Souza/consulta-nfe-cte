import customtkinter as ctk


def fazer_chip(parent, cor_texto: str, cor_fundo: str) -> ctk.CTkLabel:
    frame = ctk.CTkFrame(parent, fg_color=cor_fundo, corner_radius=20)
    frame.pack(side="left", padx=(0, 8))
    lbl = ctk.CTkLabel(frame, text="", text_color=cor_texto, font=ctk.CTkFont(size=11))
    lbl.pack(padx=12, pady=3)
    return lbl
