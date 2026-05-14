from typing import Callable

import customtkinter as ctk


class PainelHistorico:
    def __init__(self, parent, on_restaurar: Callable[[dict], None]):
        self._historico: list[dict] = []
        self._visible = False
        self._on_restaurar = on_restaurar

        self._btn_toggle = ctk.CTkButton(
            parent, text="▶  Histórico (0)",
            fg_color="transparent", hover_color="#444",
            anchor="w", height=28,
            command=self._toggle,
        )
        self._btn_toggle.pack(fill="x", pady=(10, 0))
        self._scroll = ctk.CTkScrollableFrame(parent, height=88)

    def adicionar(self, entry: dict) -> None:
        self._historico.insert(0, entry)
        self._update_btn()
        self._rebuild()

    def _toggle(self) -> None:
        self._visible = not self._visible
        self._update_btn()
        if self._visible:
            self._scroll.pack(fill="x", pady=(2, 0))
        else:
            self._scroll.pack_forget()

    def _rebuild(self) -> None:
        for w in self._scroll.winfo_children():
            w.destroy()
        for entry in self._historico:
            ctk.CTkButton(
                self._scroll,
                text=entry["label"],
                fg_color="transparent", hover_color="#3a3a3a",
                anchor="w", height=28,
                command=lambda e=entry: self._on_restaurar(e),
            ).pack(fill="x", pady=1)

    def _update_btn(self) -> None:
        prefix = "▼" if self._visible else "▶"
        self._btn_toggle.configure(text=f"{prefix}  Histórico ({len(self._historico)})")
