import requests
import customtkinter as ctk

from config import ICON_PATH
from ui.login_frame import LoginFrame
from ui.busca_frame import BuscaFrame


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Consulta NF-e / CT-e")
        self.geometry("520x500")
        self.resizable(True, True)

        if ICON_PATH.exists():
            self.iconbitmap(str(ICON_PATH))

        self.session = requests.Session()
        self.session.cookies.set("timezone-offset", "180")

        self._busca_frame = None
        self._login_frame = LoginFrame(self, on_success=self._mostrar_busca)
        self._login_frame.pack(fill="both", expand=True)

    def _mostrar_busca(self, usuario_nome: str) -> None:
        self._login_frame.pack_forget()
        self._busca_frame = BuscaFrame(
            self, self.session, usuario_nome, on_logout=self._voltar_login
        )
        self._busca_frame.pack(fill="both", expand=True)
        self.geometry("920x680")
        self.resizable(True, True)
        self.minsize(700, 520)

    def _voltar_login(self) -> None:
        self.session.cookies.clear()
        self.session.cookies.set("timezone-offset", "180")
        if self._busca_frame:
            self._busca_frame.destroy()
            self._busca_frame = None
        self._login_frame.reset()
        self._login_frame.pack(fill="both", expand=True)
        self.geometry("520x500")
        self.resizable(False, False)
