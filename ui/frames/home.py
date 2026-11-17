import customtkinter as ctk

from ui import theme
from ui.widgets.nav_card import NavCard
from ui.widgets.topbar import make_topbar


class HomeFrame(ctk.CTkFrame):
    def __init__(self, parent, user_name: str, on_search, on_upload, on_logout):
        super().__init__(parent, fg_color=theme.BG, corner_radius=0)
        self._on_logout = on_logout
        self._build(user_name, on_search, on_upload)

    def _build(self, user_name: str, on_search, on_upload) -> None:
        make_topbar(self, "Canhotos", user_name, self._on_logout)

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True)
        content = ctk.CTkFrame(body, fg_color="transparent")
        content.place(relx=0.5, rely=0.5, anchor="center", relwidth=1.0)

        ctk.CTkLabel(
            content, text="O que deseja fazer?", text_color=theme.TEXT,
            font=theme.font(theme.FONT_SIZE_LG, "bold"), anchor="w",
        ).pack(fill="x", padx=48, pady=(0, theme.SPACE_SM))

        NavCard(
            content, icon="file-search", tone="ok",
            title="Consulta NF-e / CT-e",
            description="Veja CT-e e imagem de uma faixa de NF-es",
            command=on_search,
        ).pack(fill="x", padx=48, pady=(0, 14))

        NavCard(
            content, icon="upload", tone="info",
            title="Upload de canhotos",
            description="Renomeie as fotos por OCR e envie ao sistema",
            command=on_upload,
        ).pack(fill="x", padx=48)
