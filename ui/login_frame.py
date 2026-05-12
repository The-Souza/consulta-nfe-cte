import threading

import customtkinter as ctk

import api
import credentials
from config import APP_SUBTITULO


class LoginFrame(ctk.CTkFrame):
    def __init__(self, parent, on_success):
        super().__init__(parent, fg_color="transparent")
        self._session    = parent.session
        self._on_success = on_success
        self._build()

    def _build(self) -> None:
        card = ctk.CTkFrame(self, corner_radius=14)
        card.place(relx=0.5, rely=0.5, anchor="center")

        ctk.CTkLabel(
            card, text="Consulta NF-e / CT-e",
            font=ctk.CTkFont(size=22, weight="bold"),
        ).pack(padx=48, pady=(34, 4))

        if APP_SUBTITULO:
            ctk.CTkLabel(
                card, text=APP_SUBTITULO,
                font=ctk.CTkFont(size=12), text_color="gray",
            ).pack(padx=48, pady=(0, 28))

        ctk.CTkLabel(card, text="E-mail", anchor="w").pack(anchor="w", padx=48)
        self.entry_email = ctk.CTkEntry(
            card, width=340, height=40, placeholder_text="seu@email.com"
        )
        self.entry_email.pack(padx=48, pady=(4, 16))

        ctk.CTkLabel(card, text="Senha", anchor="w").pack(anchor="w", padx=48)
        self.entry_senha = ctk.CTkEntry(
            card, width=340, height=40, show="*", placeholder_text="••••••••"
        )
        self.entry_senha.pack(padx=48, pady=(4, 28))

        self.btn_entrar = ctk.CTkButton(
            card, text="Entrar",
            width=340, height=44,
            font=ctk.CTkFont(size=14, weight="bold"),
            command=self._fazer_login,
        )
        self.btn_entrar.pack(padx=48)

        self.lbl_erro = ctk.CTkLabel(
            card, text="", text_color="#FF6B6B", wraplength=320
        )
        self.lbl_erro.pack(pady=(12, 28))

        self.entry_email.bind("<Return>", lambda e: self.entry_senha.focus())
        self.entry_senha.bind("<Return>", lambda e: self._fazer_login())
        self._preencher_credenciais()

    def _preencher_credenciais(self) -> None:
        email, senha = credentials.carregar()
        if email:
            self.entry_email.insert(0, email)
        if senha:
            self.entry_senha.insert(0, senha)

    def reset(self) -> None:
        self.entry_email.delete(0, "end")
        self.entry_senha.delete(0, "end")
        self.lbl_erro.configure(text="")
        self.btn_entrar.configure(state="normal", text="Entrar")
        self._preencher_credenciais()

    def _fazer_login(self) -> None:
        email = self.entry_email.get().strip()
        senha = self.entry_senha.get()
        if not email or not senha:
            self.lbl_erro.configure(text="Preencha e-mail e senha.")
            return
        self.btn_entrar.configure(state="disabled", text="Entrando...")
        self.lbl_erro.configure(text="")
        threading.Thread(target=self._login_thread, args=(email, senha), daemon=True).start()

    def _login_thread(self, email: str, senha: str) -> None:
        try:
            nome = api.fazer_login(self._session, email, senha)
            credentials.salvar(email, senha)
            self.after(0, self._on_success, nome)
        except ValueError as e:
            self.after(0, self._set_erro, str(e))
        except Exception as e:
            self.after(0, self._set_erro, f"Erro de conexão: {e}")

    def _set_erro(self, msg: str) -> None:
        self.lbl_erro.configure(text=msg)
        self.btn_entrar.configure(state="normal", text="Entrar")
