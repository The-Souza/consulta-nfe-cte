import customtkinter as ctk


class HomeFrame(ctk.CTkFrame):
    def __init__(self, parent, usuario_nome: str, on_consulta, on_upload, on_logout):
        super().__init__(parent, fg_color="transparent")
        self._on_logout = on_logout
        self._build(usuario_nome, on_consulta, on_upload)

    def _build(self, usuario_nome: str, on_consulta, on_upload) -> None:
        topbar = ctk.CTkFrame(self, height=40, corner_radius=0)
        topbar.pack(fill="x")
        topbar.pack_propagate(False)

        ctk.CTkLabel(
            topbar, text="Canhotos",
            font=ctk.CTkFont(size=14, weight="bold"),
        ).pack(side="left", padx=16)

        ctk.CTkButton(
            topbar, text="Sair", width=72, height=32,
            fg_color="transparent", hover_color="#444",
            border_width=1, border_color="gray",
            command=self._on_logout,
        ).pack(side="right", padx=14, pady=9)

        if usuario_nome:
            ctk.CTkLabel(
                topbar, text=f"Olá, {usuario_nome} ·",
                font=ctk.CTkFont(size=12), text_color="gray",
            ).pack(side="right", padx=(4, 0))

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
