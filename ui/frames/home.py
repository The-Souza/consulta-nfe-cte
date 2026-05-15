import customtkinter as ctk

from ui.widgets.topbar import fazer_topbar


class HomeFrame(ctk.CTkFrame):
    def __init__(self, parent, usuario_nome: str, on_consulta, on_upload, on_logout):
        super().__init__(parent, fg_color="transparent")
        self._on_logout = on_logout
        self._build(usuario_nome, on_consulta, on_upload)

    def _build(self, usuario_nome: str, on_consulta, on_upload) -> None:
        fazer_topbar(self, "Canhotos", usuario_nome, self._on_logout)

        center = ctk.CTkFrame(self, fg_color="transparent")
        center.place(relx=0.5, rely=0.5, anchor="center")

        ctk.CTkLabel(
            center, text="O que deseja fazer?",
            font=ctk.CTkFont(size=18, weight="bold"),
        ).pack(pady=(0, 32))

        ctk.CTkButton(
            center,
            text="Consulta NF-e / CT-e",
            width=280, height=64,
            font=ctk.CTkFont(size=14, weight="bold"),
            command=on_consulta,
        ).pack(pady=(0, 16))

        ctk.CTkButton(
            center,
            text="Upload Canhotos",
            width=280, height=64,
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color="#1a6b35", hover_color="#145429",
            command=on_upload,
        ).pack()
