from typing import Callable

import customtkinter as ctk


def fazer_topbar(parent, titulo: str, usuario_nome: str, on_sair: Callable) -> None:
    topbar = ctk.CTkFrame(parent, height=40, corner_radius=0)
    topbar.pack(fill="x")
    topbar.pack_propagate(False)

    ctk.CTkLabel(
        topbar, text=titulo,
        font=ctk.CTkFont(size=14, weight="bold"),
    ).pack(side="left", padx=16)

    ctk.CTkButton(
        topbar, text="Sair", width=72, height=32,
        fg_color="transparent", hover_color="#444",
        border_width=1, border_color="gray",
        command=on_sair,
    ).pack(side="right", padx=14, pady=9)

    if usuario_nome:
        ctk.CTkLabel(
            topbar, text=f"Olá, {usuario_nome} ·",
            font=ctk.CTkFont(size=12), text_color="gray",
        ).pack(side="right", padx=(4, 0))
