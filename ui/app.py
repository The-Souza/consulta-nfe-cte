import requests
import customtkinter as ctk

from config import ICON_FILE
from ui.frames.login import LoginFrame
from ui.frames.home import HomeFrame
from ui.frames.search import SearchFrame
from ui.frames.upload import UploadFrame


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Canhotos")
        self.geometry("520x500")
        self.resizable(False, False)

        if ICON_FILE.exists():
            self.iconbitmap(str(ICON_FILE))

        self.session = requests.Session()
        self.session.cookies.set("timezone-offset", "180")

        self._user_name     = ""
        self._home_frame    = None
        self._search_frame  = None
        self._upload_frame  = None

        self._login_frame = LoginFrame(self, on_success=self._show_home)
        self._login_frame.pack(fill="both", expand=True)

    # ------------------------------------------------------------------
    # NAVEGAÇÃO
    # ------------------------------------------------------------------

    def _show_home(self, user_name: str) -> None:
        self._user_name = user_name
        self._login_frame.pack_forget()
        self.geometry("520x500")
        self.resizable(False, False)
        self._home_frame = HomeFrame(
            self,
            user_name=user_name,
            on_search=self._show_search,
            on_upload=self._show_upload,
            on_logout=self._back_to_login,
        )
        self._home_frame.pack(fill="both", expand=True)

    def _show_search(self) -> None:
        if self._home_frame:
            self._home_frame.pack_forget()
        self.geometry("920x680")
        self.resizable(True, True)
        self.minsize(700, 520)
        self._search_frame = SearchFrame(
            self, self.session, self._user_name,
            on_logout=self._back_to_login,
            on_back=self._back_to_home,
        )
        self._search_frame.pack(fill="both", expand=True)

    def _show_upload(self) -> None:
        if self._home_frame:
            self._home_frame.pack_forget()
        self.geometry("920x720")
        self.resizable(True, True)
        self.minsize(700, 560)
        self._upload_frame = UploadFrame(
            self, self.session, self._user_name,
            on_logout=self._back_to_login,
            on_back=self._back_to_home,
        )
        self._upload_frame.pack(fill="both", expand=True)

    def _back_to_home(self) -> None:
        for frame in (self._search_frame, self._upload_frame):
            if frame:
                frame.destroy()
        self._search_frame = None
        self._upload_frame = None
        self.geometry("520x500")
        self.resizable(False, False)
        if self._home_frame:
            self._home_frame.pack(fill="both", expand=True)

    def _back_to_login(self) -> None:
        self.session.cookies.clear()
        self.session.cookies.set("timezone-offset", "180")

        for frame in (self._home_frame, self._search_frame, self._upload_frame):
            if frame:
                frame.destroy()
        self._home_frame   = None
        self._search_frame = None
        self._upload_frame = None

        self._login_frame.reset()
        self._login_frame.pack(fill="both", expand=True)
        self.geometry("520x500")
        self.resizable(False, False)
