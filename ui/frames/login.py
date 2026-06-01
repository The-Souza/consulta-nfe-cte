import threading

import customtkinter as ctk

import api
import credentials
from config import APP_SUBTITLE


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

        if APP_SUBTITLE:
            ctk.CTkLabel(
                card, text=APP_SUBTITLE,
                font=ctk.CTkFont(size=12), text_color="gray",
            ).pack(padx=48, pady=(0, 28))

        ctk.CTkLabel(card, text="E-mail", anchor="w").pack(anchor="w", padx=48)
        self.entry_email = ctk.CTkEntry(
            card, width=340, height=40, placeholder_text="seu@email.com"
        )
        self.entry_email.pack(padx=48, pady=(4, 16))

        ctk.CTkLabel(card, text="Senha", anchor="w").pack(anchor="w", padx=48)
        self.entry_password = ctk.CTkEntry(
            card, width=340, height=40, show="*", placeholder_text="••••••••"
        )
        self.entry_password.pack(padx=48, pady=(4, 28))

        self.btn_login = ctk.CTkButton(
            card, text="Entrar",
            width=340, height=44,
            font=ctk.CTkFont(size=14, weight="bold"),
            command=self._do_login,
        )
        self.btn_login.pack(padx=48)

        self.lbl_error = ctk.CTkLabel(
            card, text="", text_color="#FF6B6B", wraplength=320
        )
        self.lbl_error.pack(pady=(12, 28))

        self.entry_email.bind("<Return>", lambda e: self.entry_password.focus())
        self.entry_password.bind("<Return>", lambda e: self._do_login())
        self._fill_credentials()

    def _fill_credentials(self) -> None:
        email, password = credentials.load()
        if email:
            self.entry_email.insert(0, email)
        if password:
            self.entry_password.insert(0, password)

    def reset(self) -> None:
        self.entry_email.delete(0, "end")
        self.entry_password.delete(0, "end")
        self.lbl_error.configure(text="")
        self.btn_login.configure(state="normal", text="Entrar")
        self._fill_credentials()

    def _do_login(self) -> None:
        email = self.entry_email.get().strip()
        password = self.entry_password.get()
        if not email or not password:
            self.lbl_error.configure(text="Preencha e-mail e senha.")
            return
        self.btn_login.configure(state="disabled", text="Entrando...")
        self.lbl_error.configure(text="")
        threading.Thread(target=self._login_thread, args=(email, password), daemon=True).start()

    def _login_thread(self, email: str, password: str) -> None:
        try:
            name = api.login(self._session, email, password)
            credentials.save(email, password)
            self.after(0, self._on_success, name)
        except ValueError as e:
            self.after(0, self._set_error, str(e))
        except Exception as e:
            self.after(0, self._set_error, api.friendly_error(e))

    def _set_error(self, msg: str) -> None:
        self.lbl_error.configure(text=msg)
        self.btn_login.configure(state="normal", text="Entrar")
