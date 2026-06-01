from typing import Callable

import customtkinter as ctk


def make_topbar(parent, title: str, user_name: str, on_logout: Callable, on_back: Callable | None = None) -> None:
    topbar = ctk.CTkFrame(parent, height=40, corner_radius=0)
    topbar.pack(fill="x")
    topbar.pack_propagate(False)

    if on_back:
        ctk.CTkButton(
            topbar, text="← Voltar", width=90, height=32,
            fg_color="transparent", hover_color="#444",
            border_width=1, border_color="gray",
            command=on_back,
        ).pack(side="left", padx=(14, 0), pady=9)

    ctk.CTkLabel(
        topbar, text=title,
        font=ctk.CTkFont(size=14, weight="bold"),
    ).pack(side="left", padx=16)

    ctk.CTkButton(
        topbar, text="Sair", width=72, height=32,
        fg_color="transparent", hover_color="#444",
        border_width=1, border_color="gray",
        command=on_logout,
    ).pack(side="right", padx=14, pady=9)

    if user_name:
        ctk.CTkLabel(
            topbar, text=f"Olá, {user_name} ·",
            font=ctk.CTkFont(size=12), text_color="gray",
        ).pack(side="right", padx=(4, 0))
