import customtkinter as ctk

from ui.widgets.topbar import make_topbar


class HomeFrame(ctk.CTkFrame):
    def __init__(self, parent, user_name: str, on_search, on_upload, on_logout):
        super().__init__(parent, fg_color="transparent")
        self._on_logout = on_logout
        self._build(user_name, on_search, on_upload)

    def _build(self, user_name: str, on_search, on_upload) -> None:
        make_topbar(self, "Canhotos", user_name, self._on_logout)

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
            command=on_search,
        ).pack(pady=(0, 16))

        ctk.CTkButton(
            center,
            text="Upload Canhotos",
            width=280, height=64,
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color="#1a6b35", hover_color="#145429",
            command=on_upload,
        ).pack()
