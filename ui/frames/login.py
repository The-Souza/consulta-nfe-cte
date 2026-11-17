import threading

import customtkinter as ctk

import api
import credentials
from config import APP_SUBTITLE, APP_VERSION, ICON_FILE
from ui import theme
from ui.icons import get_icon, load_logo

_CARD_PAD = theme.SPACE_XXL
_CARD_PAD_Y = 28
_FIELD_GAP = 14
_FIELD_WIDTH = 316
_LOGO_SIZE = 44


class LoginFrame(ctk.CTkFrame):
    def __init__(self, parent, on_success):
        super().__init__(parent, fg_color=theme.BG, corner_radius=0)
        self._session    = parent.session
        self._on_success = on_success
        self._password_visible = False
        self._build()

    def _build(self) -> None:
        card = ctk.CTkFrame(
            self, fg_color=theme.SURFACE, border_color=theme.BORDER, border_width=1,
            corner_radius=theme.RADIUS_DIALOG,
        )
        # Slightly above center to leave room for the version label at the bottom.
        card.place(relx=0.5, rely=0.48, anchor="center")

        self._build_header(card)
        self.entry_email = self._build_field(card, "E-mail", "seu@email.com")
        self.entry_password = self._build_field(card, "Senha", "••••••••", show="•")
        self._build_password_toggle()

        self.remember_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(
            card, text="Lembrar acesso neste computador", variable=self.remember_var,
            checkbox_width=16, checkbox_height=16, corner_radius=4, border_width=1,
            fg_color=theme.PRIMARY, hover_color=theme.PRIMARY_HOVER, border_color=theme.BORDER_INPUT,
            text_color=theme.TEXT_LABEL, font=theme.font(theme.FONT_SIZE_BODY),
        ).pack(anchor="w", padx=_CARD_PAD, pady=(0, _FIELD_GAP + 2))

        self.btn_login = ctk.CTkButton(
            card, text="Entrar", width=_FIELD_WIDTH, height=44,
            corner_radius=theme.RADIUS_INPUT, fg_color=theme.PRIMARY, hover_color=theme.PRIMARY_HOVER,
            text_color=theme.TEXT_ON_PRIMARY, font=theme.font(theme.FONT_SIZE_MD, "bold"),
            command=self._do_login,
        )
        self.btn_login.pack(padx=_CARD_PAD, pady=(0, _CARD_PAD_Y))

        self.lbl_error = ctk.CTkLabel(
            card, text="", text_color=theme.STATUS["error"][0], wraplength=_FIELD_WIDTH,
            font=theme.font(theme.FONT_SIZE_BODY),
        )

        ctk.CTkLabel(
            self, text=f"v{APP_VERSION}", text_color=theme.TEXT_MUTED, height=16,
            font=theme.font(theme.FONT_SIZE_XS),
        ).place(relx=0.5, rely=1.0, y=-theme.SPACE_SM, anchor="s")

        self.entry_email.bind("<Return>", lambda e: self.entry_password.focus())
        self.entry_password.bind("<Return>", lambda e: self._do_login())
        self._fill_credentials()

    def _build_header(self, card: ctk.CTkFrame) -> None:
        header = ctk.CTkFrame(card, fg_color="transparent")
        header.pack(padx=_CARD_PAD, pady=(_CARD_PAD_Y, theme.SPACE_LG + theme.SPACE_XS))

        self._build_logo(header).pack(pady=(0, theme.SPACE_MD))
        ctk.CTkLabel(
            header, text="Consulta NF-e / CT-e", text_color=theme.TEXT,
            font=theme.font(theme.FONT_SIZE_XL, "bold"),
        ).pack()
        if APP_SUBTITLE:
            ctk.CTkLabel(
                header, text=APP_SUBTITLE, text_color=theme.TEXT_MUTED,
                font=theme.font(theme.FONT_SIZE_BODY),
            ).pack(pady=(theme.SPACE_XS, 0))

    def _build_logo(self, parent: ctk.CTkFrame) -> ctk.CTkBaseClass:
        logo = load_logo(ICON_FILE, _LOGO_SIZE * 2)
        if logo is not None:
            image = ctk.CTkImage(light_image=logo, dark_image=logo, size=(_LOGO_SIZE, _LOGO_SIZE))
            return ctk.CTkLabel(parent, text="", image=image)

        return ctk.CTkLabel(
            parent, text="", width=_LOGO_SIZE, height=_LOGO_SIZE,
            fg_color=theme.PRIMARY, corner_radius=theme.RADIUS_CARD,
            image=get_icon("file-check", 24, theme.TEXT_ON_PRIMARY),
        )

    def _build_field(self, card: ctk.CTkFrame, label: str, placeholder: str, show: str = "") -> ctk.CTkEntry:
        ctk.CTkLabel(
            card, text=label, text_color=theme.TEXT_LABEL, font=theme.font(theme.FONT_SIZE_BODY),
            anchor="w", height=18,
        ).pack(anchor="w", padx=_CARD_PAD)
        entry = ctk.CTkEntry(
            card, width=_FIELD_WIDTH, height=40, show=show, placeholder_text=placeholder,
            corner_radius=theme.RADIUS_INPUT, border_width=1,
            fg_color=theme.INPUT_BG, border_color=theme.BORDER_INPUT,
            text_color=theme.TEXT, placeholder_text_color=theme.TEXT_MUTED,
            font=theme.font(theme.FONT_SIZE_INPUT),
        )
        entry.pack(padx=_CARD_PAD, pady=(theme.SPACE_XS + 2, _FIELD_GAP))
        return entry

    def _build_password_toggle(self) -> None:
        self.btn_toggle_password = ctk.CTkButton(
            self.entry_password, text="", width=32, height=32,
            corner_radius=theme.RADIUS_INPUT - 2,
            fg_color=theme.INPUT_BG, hover_color=theme.SURFACE_2,
            image=get_icon("eye", 18, theme.TEXT_MUTED),
            command=self._toggle_password,
        )
        self.btn_toggle_password.place(relx=1.0, rely=0.5, x=-4, anchor="e")

    def _toggle_password(self) -> None:
        self._password_visible = not self._password_visible
        self.entry_password.configure(show="" if self._password_visible else "•")
        icon = "eye-off" if self._password_visible else "eye"
        self.btn_toggle_password.configure(image=get_icon(icon, 18, theme.TEXT_MUTED))

    def _fill_credentials(self) -> None:
        email, password = credentials.load()
        if email:
            self.entry_email.insert(0, email)
        if password:
            self.entry_password.insert(0, password)

    def reset(self) -> None:
        self.entry_email.delete(0, "end")
        self.entry_password.delete(0, "end")
        if self._password_visible:
            self._toggle_password()
        self.remember_var.set(True)
        self._show_error("")
        self.btn_login.configure(state="normal", text="Entrar")
        self._fill_credentials()

    def _do_login(self) -> None:
        email = self.entry_email.get().strip()
        password = self.entry_password.get()
        if not email or not password:
            self._show_error("Preencha e-mail e senha.")
            return
        self.btn_login.configure(state="disabled", text="Entrando...")
        self._show_error("")
        remember = self.remember_var.get()
        threading.Thread(target=self._login_thread, args=(email, password, remember), daemon=True).start()

    def _login_thread(self, email: str, password: str, remember: bool) -> None:
        try:
            name = api.login(self._session, email, password)
            if remember:
                credentials.save(email, password)
            else:
                credentials.forget_password(email)
            self.after(0, self._on_success, name)
        except ValueError as e:
            self.after(0, self._set_error, str(e))
        except Exception as e:
            self.after(0, self._set_error, api.friendly_error(e))

    def _show_error(self, msg: str) -> None:
        self.lbl_error.configure(text=msg)
        if msg:
            self.lbl_error.pack(padx=_CARD_PAD, pady=(0, theme.SPACE_MD))
            self.btn_login.pack_configure(pady=(0, theme.SPACE_SM))
        else:
            self.lbl_error.pack_forget()
            self.btn_login.pack_configure(pady=(0, _CARD_PAD_Y))

    def _set_error(self, msg: str) -> None:
        self._show_error(msg)
        self.btn_login.configure(state="normal", text="Entrar")
