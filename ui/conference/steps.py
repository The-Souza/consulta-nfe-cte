import customtkinter as ctk

from ui import theme

STEPS = ("Carregar fotos", "Conferir NF-e e data", "Enviar")
_ACTIVE_BORDER = theme.STATUS["ok"][0]


class Steps(ctk.CTkFrame):
    """The "1 Carregar fotos · 2 Conferir NF-e e data · 3 Enviar" header, with one step highlighted."""

    def __init__(self, parent):
        super().__init__(parent, fg_color=theme.TRANSPARENT)
        self._pills: list[tuple[ctk.CTkFrame, ctk.CTkLabel, ctk.CTkLabel]] = []
        for number, text in enumerate(STEPS, start=1):
            if number > 1:
                ctk.CTkFrame(self, width=28, height=2, corner_radius=0, fg_color=theme.BORDER).pack(
                    side="left", padx=theme.SPACE_MD,
                )
            pill = ctk.CTkFrame(self, height=30, corner_radius=15, border_width=1)
            pill.pack(side="left")
            circle = ctk.CTkLabel(
                pill, text=str(number), width=20, height=20, corner_radius=10,
                font=theme.font(theme.FONT_SIZE_SM, "bold"),
            )
            circle.pack(side="left", padx=(6, theme.SPACE_SM), pady=4)
            label = ctk.CTkLabel(pill, text=text, height=20, font=theme.font(theme.FONT_SIZE_BODY, "bold"))
            label.pack(side="left", padx=(0, theme.SPACE_MD))
            self._pills.append((pill, circle, label))

    def set_active(self, step: int) -> None:
        for number, (pill, circle, label) in enumerate(self._pills, start=1):
            active = number == step
            pill.configure(
                fg_color=theme.SURFACE_2 if active else theme.BG,
                border_color=_ACTIVE_BORDER if active else theme.BORDER,
            )
            circle.configure(
                fg_color=theme.TEXT if active else theme.STATUS["neutral"][1],
                text_color=theme.BG if active else theme.TEXT_MUTED,
            )
            label.configure(text_color=theme.TEXT if active else theme.TEXT_MUTED)
