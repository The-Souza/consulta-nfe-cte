import requests
import customtkinter as ctk

from config import ICON_PATH
from ui.login_frame import LoginFrame
from ui.home_frame import HomeFrame
from ui.busca_frame import BuscaFrame
from ui.upload_frame import UploadFrame


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Canhotos")
        self.geometry("520x500")
        self.resizable(False, False)

        if ICON_PATH.exists():
            self.iconbitmap(str(ICON_PATH))

        self.session = requests.Session()
        self.session.cookies.set("timezone-offset", "180")

        self._usuario_nome  = ""
        self._home_frame    = None
        self._busca_frame   = None
        self._upload_frame  = None

        self._login_frame = LoginFrame(self, on_success=self._mostrar_home)
        self._login_frame.pack(fill="both", expand=True)

    # ------------------------------------------------------------------
    # NAVEGAÇÃO
    # ------------------------------------------------------------------

    def _mostrar_home(self, usuario_nome: str) -> None:
        self._usuario_nome = usuario_nome
        self._login_frame.pack_forget()
        self.geometry("520x500")
        self.resizable(False, False)
        self._home_frame = HomeFrame(
            self,
            usuario_nome=usuario_nome,
            on_consulta=self._mostrar_busca,
            on_upload=self._mostrar_upload,
            on_logout=self._voltar_login,
        )
        self._home_frame.pack(fill="both", expand=True)

    def _mostrar_busca(self) -> None:
        if self._home_frame:
            self._home_frame.pack_forget()
        self.geometry("920x680")
        self.resizable(True, True)
        self.minsize(700, 520)
        self._busca_frame = BuscaFrame(
            self, self.session, self._usuario_nome,
            on_logout=self._voltar_login,
        )
        self._busca_frame.pack(fill="both", expand=True)

    def _mostrar_upload(self) -> None:
        if self._home_frame:
            self._home_frame.pack_forget()
        self.geometry("920x720")
        self.resizable(True, True)
        self.minsize(700, 560)
        self._upload_frame = UploadFrame(
            self, self.session, self._usuario_nome,
            on_logout=self._voltar_login,
        )
        self._upload_frame.pack(fill="both", expand=True)

    def _voltar_login(self) -> None:
        self.session.cookies.clear()
        self.session.cookies.set("timezone-offset", "180")

        for frame in (self._home_frame, self._busca_frame, self._upload_frame):
            if frame:
                frame.destroy()
        self._home_frame   = None
        self._busca_frame  = None
        self._upload_frame = None

        self._login_frame.reset()
        self._login_frame.pack(fill="both", expand=True)
        self.geometry("520x500")
        self.resizable(False, False)
