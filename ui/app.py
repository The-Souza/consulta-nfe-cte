import requests
import customtkinter as ctk

import api
from config import ICON_FILE
from ui.frames.login import LoginFrame
from ui.frames.home import HomeFrame
from ui.frames.search import SearchFrame
from ui.frames.upload import UploadFrame
from ui.titlebar import apply_titlebar
from ui.window_size import fit_window, work_area


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Canhotos")
        self.geometry("520x500")
        self.resizable(False, False)

        if ICON_FILE.exists():
            self.iconbitmap(str(ICON_FILE))

        # Deferred so it runs after CustomTkinter applies its own title bar mode on startup.
        self.after(0, apply_titlebar, self)

        self.session = requests.Session()
        self.session.cookies.set("timezone-offset", "180")

        self._user_name     = ""
        # Kept only in memory, to log in again when the session expires mid-task (never written to disk).
        self._credentials: tuple[str, str] | None = None
        self._home_frame    = None
        self._search_frame  = None
        self._upload_frame  = None

        self._login_frame = LoginFrame(self, on_success=self._show_home)
        self._login_frame.pack(fill="both", expand=True)

    # ------------------------------------------------------------------
    # NAVEGAÇÃO
    # ------------------------------------------------------------------

    def _relogin(self) -> None:
        """Called from worker threads; only touches the session, never widgets."""
        if self._credentials is None:
            raise RuntimeError("no credentials in memory")
        api.login(self.session, *self._credentials)

    def _show_home(self, user_name: str, email: str, password: str) -> None:
        self._user_name = user_name
        self._credentials = (email, password)
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
        self._large_window(1180, 760, 1000, 640)
        self._search_frame = SearchFrame(
            self, self.session, self._user_name,
            on_logout=self._back_to_login,
            on_back=self._back_to_home,
            relogin=self._relogin,
        )
        self._search_frame.pack(fill="both", expand=True)

    def _show_upload(self) -> None:
        if self._home_frame:
            self._home_frame.pack_forget()
        self._large_window(920, 720, 700, 560)
        self._upload_frame = UploadFrame(
            self, self.session, self._user_name,
            on_logout=self._back_to_login,
            on_back=self._back_to_home,
            relogin=self._relogin,
        )
        self._upload_frame.pack(fill="both", expand=True)

    def _back_to_home(self) -> None:
        for frame in (self._search_frame, self._upload_frame):
            if frame:
                frame.destroy()
        self._search_frame = None
        self._upload_frame = None
        self._compact_window()
        if self._home_frame:
            self._home_frame.pack(fill="both", expand=True)

    def _back_to_login(self) -> None:
        self._credentials = None
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
        self._compact_window()

    def _large_window(self, width: int, height: int, min_width: int, min_height: int) -> None:
        """Search/Upload size, reduced to fit small or zoomed screens (e.g. 1366×768 laptops)."""
        fit = fit_window(
            width=width, height=height, min_width=min_width, min_height=min_height,
            area=work_area(self), scaling=ctk.ScalingTracker.get_window_scaling(self),
        )
        self.resizable(True, True)
        self.minsize(fit.min_width, fit.min_height)
        self.geometry(f"{fit.width}x{fit.height}+{fit.x}+{fit.y}")

    def _compact_window(self) -> None:
        """Login/Home size. The minimum set by Search/Upload must go too, or Tk keeps the window wide."""
        self.minsize(1, 1)
        self.geometry("520x500")
        self.resizable(False, False)
