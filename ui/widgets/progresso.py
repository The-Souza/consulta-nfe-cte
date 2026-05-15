import customtkinter as ctk


def fazer_progresso(parent) -> tuple[ctk.CTkLabel, ctk.CTkProgressBar]:
    lbl = ctk.CTkLabel(parent, text="", anchor="w")
    lbl.pack(fill="x", pady=(4, 2))
    pb = ctk.CTkProgressBar(parent)
    pb.pack(fill="x", pady=(0, 8))
    pb.set(0)
    return lbl, pb
