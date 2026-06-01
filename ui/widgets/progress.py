import customtkinter as ctk


def make_progress(parent) -> tuple[ctk.CTkLabel, ctk.CTkProgressBar]:
    label = ctk.CTkLabel(parent, text="", anchor="w")
    label.pack(fill="x", pady=(4, 2))
    progress_bar = ctk.CTkProgressBar(parent)
    progress_bar.pack(fill="x", pady=(0, 8))
    progress_bar.set(0)
    return label, progress_bar
