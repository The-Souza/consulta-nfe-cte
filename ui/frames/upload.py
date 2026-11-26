from typing import Callable

import customtkinter as ctk

from ui import theme
from ui.conference.view import ConferenceView
from ui.frames.upload_legacy import LegacyUploadFrame


class UploadFrame(ctk.CTkFrame):
    """Opens the new review (D1) and switches to the old Renomear → Enviar flow and back, until 2.0.0-alpha.7."""

    def __init__(self, parent, session, user_name: str, on_logout: Callable[[], None],
                 on_back: Callable[[], None] | None = None, relogin: Callable[[], None] | None = None):
        super().__init__(parent, fg_color=theme.BG, corner_radius=0)
        self._session   = session
        self._user_name = user_name
        self._on_logout = on_logout
        self._on_back   = on_back
        self._relogin   = relogin
        self._screen: ctk.CTkFrame | None = None
        self._show_new()

    def _show_new(self) -> None:
        self._swap(ConferenceView(
            self, self._user_name, on_logout=self._on_logout, on_back=self._on_back, on_legacy=self._show_legacy,
        ))

    def _show_legacy(self) -> None:
        self._swap(LegacyUploadFrame(
            self, self._session, self._user_name, on_logout=self._on_logout, on_back=self._on_back,
            relogin=self._relogin, on_new_flow=self._show_new,
        ))

    def _swap(self, screen: ctk.CTkFrame) -> None:
        if self._screen is not None:
            self._screen.destroy()
        self._screen = screen
        screen.pack(fill="both", expand=True)
