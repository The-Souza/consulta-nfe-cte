"""The "Enviar planilha" window (design/EnviarPlanilha.dc.html). The logic lives in sync/report; this file only
draws and wires it. Network and file reading run in a thread; the UI is touched only through after()."""
import logging
import os
import tempfile
import threading
import tkinter
from datetime import datetime
from pathlib import Path
from tkinter import filedialog

import customtkinter as ctk

from sheet_sync.columns import choose_columns, saved_columns_valid
from sheet_sync.icon import save_icon
from sheet_sync.report import (
    NO_COLUMN,
    column_options,
    count_label,
    ignored_lines,
    letter_of,
    sent_label,
    title_of,
)
from sheet_sync.settings import Prefs, load_config, load_prefs, save_prefs
from sheet_sync.sheet import Columns, SheetError, read_headers
from sheet_sync.sync import SyncResult, config_error, sync
from sheet_sync.watcher import ChangeWatcher
from ui import theme
from ui.icons import get_icon
from ui.titlebar import apply_titlebar
from ui.widgets.banner import Banner
from utils.status import Tone

logger = logging.getLogger(__name__)

_WIDTH, _HEIGHT = 520, 660
_CHOOSE = "Escolha a coluna"
_FIELD_LABELS = {"nfe": "NF-e", "driver": "Motorista", "date": "Data de entrega", "cte": "CT-e (opcional)"}
_REQUIRED = ("nfe", "driver", "date")
# "Enviar sozinho": the sheet is checked every 30 s; a change is confirmed 5 s later, so a save reaches the
# table in about 35 s (the spec allows 1 minute)
_WATCH_MS = 30_000
_CONFIRM_MS = 5_000


class SendSheetWindow(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Enviar planilha")
        self.geometry(f"{_WIDTH}x{_HEIGHT}")
        self.resizable(False, False)
        self.configure(fg_color=theme.BG)
        self._set_icon()
        # Deferred so it runs after CustomTkinter applies its own title bar mode on startup
        self.after(0, apply_titlebar, self)

        self._config = load_config()
        self._prefs = load_prefs()
        self._options: list[str] = []
        self._sending = False
        self._auto_running = False  # the send in progress was started by "Enviar sozinho"
        self._send_watcher: ChangeWatcher | None = None  # the watcher that started that send
        # False when the columns on screen weren't checked by the user since they changed (re-chosen after the
        # sheet changed, or a new sheet): the automatic send waits, since it would write them unseen
        self._columns_confirmed = False
        self._watcher: ChangeWatcher | None = None
        self._watch_job: str | None = None

        self._build()
        if self._prefs.auto_send:  # before opening the sheet, which saves the prefs with the checkbox state
            self._auto.select()
        problem = config_error(self._config)
        if problem:
            self._config_banner.show(Tone.ERROR, problem, icon="x")
            for widget in (self._btn_send, self._btn_preview, self._auto):
                widget.configure(state="disabled")
        path = self._prefs.path or self._config.sheet_path
        if path:
            self._open_sheet(path, keep_columns=True)
        if self._auto.get() and not problem:
            self._start_watching()

    def resizable(self, width: bool = None, height: bool = None):
        result = super().resizable(width, height)
        # CustomTkinter re-creates the native window here and the new one comes without our color
        apply_titlebar(self)
        return result

    # ------------------------------------------------------------------
    # LAYOUT
    # ------------------------------------------------------------------

    def _set_icon(self) -> None:
        """Without iconbitmap, CustomTkinter puts its own icon on the window 200 ms after start."""
        path = Path(tempfile.gettempdir()) / "enviar-planilha.ico"  # Windows only takes a file for this
        try:
            save_icon(path)
            self.iconbitmap(str(path))
        except (OSError, tkinter.TclError):
            logger.warning("Could not set the window icon", exc_info=True)

    def _fit_height(self) -> None:
        """The result card grows with the ignored rows: grow the window instead of squeezing the card
        against the checkbox."""
        self.update_idletasks()
        scaling = ctk.ScalingTracker.get_window_scaling(self)
        needed = round(self._main.winfo_reqheight() / scaling) + 22 + theme.SPACE_XL
        self.geometry(f"{_WIDTH}x{max(_HEIGHT, needed)}")

    def _build(self) -> None:
        main = ctk.CTkFrame(self, fg_color=theme.BG, corner_radius=0)
        main.pack(fill="both", expand=True, padx=theme.SPACE_XL, pady=(22, theme.SPACE_XL))
        self._main = main

        ctk.CTkLabel(main, text="Enviar planilha de entregas", text_color=theme.TEXT, anchor="w",
                     font=theme.font(theme.FONT_SIZE_LG, "bold")).pack(fill="x")
        ctk.CTkLabel(
            main, anchor="w", justify="left", wraplength=_WIDTH - 2 * theme.SPACE_XL, text_color=theme.TEXT_MUTED,
            font=theme.font(theme.FONT_SIZE_BODY),
            text="Atualiza motorista e data de entrega para todo mundo que usa o app Canhotos. "
                 "Só este computador pode enviar.",
        ).pack(fill="x", pady=(theme.SPACE_XS, 0))

        self._config_banner = Banner(main, theme.BG)
        self._config_banner.pack(fill="x", pady=(theme.SPACE_MD, 0))

        self._build_file(main)
        self._build_columns(main)
        self._result = ctk.CTkFrame(main, corner_radius=10, border_width=1)  # packed after the first send
        self._build_result(self._result)

        self._auto = ctk.CTkCheckBox(
            main, text="Enviar sozinho quando eu salvar a planilha", command=self._on_auto_toggle,
            text_color=theme.TEXT_LABEL, text_color_disabled=theme.TEXT_MUTED, font=theme.font(theme.FONT_SIZE_BODY),
            fg_color=theme.PRIMARY, hover_color=theme.PRIMARY_HOVER, border_color=theme.BORDER_INPUT,
            checkbox_width=16, checkbox_height=16, corner_radius=4,
        )
        buttons = ctk.CTkFrame(main, fg_color=theme.TRANSPARENT)
        buttons.pack(side="bottom", fill="x")
        # Counts what a send would write, without writing: a safe first look at a sheet
        self._btn_preview = ctk.CTkButton(
            buttons, text="Conferir sem enviar", image=get_icon("file-search", 16, theme.TEXT), compound="left",
            width=0, height=44, corner_radius=theme.RADIUS_INPUT, fg_color=theme.TRANSPARENT,
            hover_color=theme.SURFACE_2, border_width=1, border_color=theme.BORDER_INPUT, text_color=theme.TEXT,
            font=theme.font(theme.FONT_SIZE_BODY), command=lambda: self._send(preview=True),
        )
        self._btn_preview.pack(side="left", padx=(0, theme.SPACE_SM))
        self._btn_send = ctk.CTkButton(
            buttons, text="Enviar agora", image=get_icon("upload", 16, theme.TEXT_ON_PRIMARY), compound="left",
            height=44, corner_radius=theme.RADIUS_INPUT, fg_color=theme.PRIMARY, hover_color=theme.PRIMARY_HOVER,
            text_color=theme.TEXT_ON_PRIMARY, font=theme.font(theme.FONT_SIZE_MD, "bold"), command=self._send,
        )
        self._btn_send.pack(side="left", fill="x", expand=True)
        self._auto.pack(side="bottom", anchor="w", pady=(0, theme.SPACE_LG))

    def _build_file(self, main: ctk.CTkFrame) -> None:
        ctk.CTkLabel(main, text="Arquivo", text_color=theme.TEXT_MUTED, anchor="w", height=18,
                     font=theme.font(theme.FONT_SIZE_SM)).pack(fill="x", pady=(theme.SPACE_LG, theme.SPACE_XS + 2))
        row = ctk.CTkFrame(main, fg_color=theme.TRANSPARENT)
        row.pack(fill="x")
        self._path = tkinter.StringVar()
        ctk.CTkEntry(
            row, textvariable=self._path, state="readonly", height=38, corner_radius=theme.RADIUS_INPUT,
            border_width=1, fg_color=theme.INPUT_BG, border_color=theme.BORDER_INPUT, text_color=theme.TEXT,
            font=theme.font(theme.FONT_SIZE_BODY, mono=True),
        ).pack(side="left", fill="x", expand=True, padx=(0, theme.SPACE_SM))
        self._btn_change = ctk.CTkButton(
            row, text="Trocar", width=0, height=38, corner_radius=theme.RADIUS_INPUT, fg_color=theme.TRANSPARENT,
            hover_color=theme.SURFACE_2, border_width=1, border_color=theme.BORDER_INPUT, text_color=theme.TEXT,
            font=theme.font(theme.FONT_SIZE_BODY), command=self._choose_file,
        )
        self._btn_change.pack(side="left")
        self._file_error = ctk.CTkLabel(main, text="", anchor="w", justify="left", height=18,
                                        text_color=theme.STATUS[Tone.ERROR.value][0], font=theme.font(theme.FONT_SIZE_SM))

    def _build_columns(self, main: ctk.CTkFrame) -> None:
        self._columns_card = ctk.CTkFrame(main, fg_color=theme.SURFACE, border_color=theme.BORDER, border_width=1,
                                          corner_radius=10)
        self._columns_card.pack(fill="x", pady=(theme.SPACE_LG, 0))
        inner = ctk.CTkFrame(self._columns_card, fg_color=theme.TRANSPARENT)
        inner.pack(fill="x", padx=14, pady=14)
        ctk.CTkLabel(inner, text="COLUNAS USADAS", text_color=theme.TEXT_MUTED, anchor="w", height=16,
                     font=theme.font(theme.FONT_SIZE_SM, "bold")).grid(row=0, column=0, columnspan=2, sticky="w")
        inner.grid_columnconfigure((0, 1), weight=1, uniform="col")

        self._menus: dict[str, ctk.CTkOptionMenu] = {}
        for index, field in enumerate(("nfe", "driver", "date", "cte")):
            cell = ctk.CTkFrame(inner, fg_color=theme.TRANSPARENT)
            cell.grid(row=1 + index // 2, column=index % 2, sticky="ew", pady=(theme.SPACE_SM, 0),
                      padx=(0, theme.SPACE_SM) if index % 2 == 0 else 0)
            ctk.CTkLabel(cell, text=_FIELD_LABELS[field], text_color=theme.TEXT_LABEL, anchor="w", height=16,
                         font=theme.font(theme.FONT_SIZE_SM)).pack(fill="x", pady=(0, theme.SPACE_XS))
            menu = ctk.CTkOptionMenu(
                cell, values=[_CHOOSE], height=34, corner_radius=theme.RADIUS_INPUT, fg_color=theme.INPUT_BG,
                button_color=theme.INPUT_BG, button_hover_color=theme.SURFACE_2, text_color=theme.TEXT,
                dropdown_fg_color=theme.SURFACE, dropdown_hover_color=theme.SURFACE_2, dropdown_text_color=theme.TEXT,
                font=theme.font(theme.FONT_SIZE_BODY), dropdown_font=theme.font(theme.FONT_SIZE_BODY),
                dynamic_resizing=False, command=lambda _value: self._on_column_picked(),
            )
            menu.set(_CHOOSE)
            menu.pack(fill="x")
            self._menus[field] = menu

    def _build_result(self, card: ctk.CTkFrame) -> None:
        inner = ctk.CTkFrame(card, fg_color=theme.TRANSPARENT)
        inner.pack(fill="x", padx=14, pady=14)
        self._result_title = ctk.CTkLabel(inner, text="", compound="left", anchor="w", justify="left",
                                          wraplength=_WIDTH - 90, font=theme.font(theme.FONT_SIZE_INPUT, "bold"))
        self._result_title.pack(fill="x")
        self._result_message = ctk.CTkLabel(inner, text="", anchor="w", justify="left", wraplength=_WIDTH - 90,
                                            font=theme.font(theme.FONT_SIZE_SM))
        self._counts = ctk.CTkFrame(inner, fg_color=theme.TRANSPARENT)
        self._counts.grid_columnconfigure((0, 1, 2), weight=1, uniform="count")
        self._count_labels: dict[str, tuple[ctk.CTkLabel, ctk.CTkLabel]] = {}
        for column, kind in enumerate(("new", "updated", "ignored")):
            cell = ctk.CTkFrame(self._counts, fg_color=theme.TRANSPARENT)
            cell.grid(row=0, column=column, sticky="w")
            number = ctk.CTkLabel(cell, text="", anchor="w", height=20, font=theme.font(theme.FONT_SIZE_LG, mono=True))
            number.pack(anchor="w")
            label = ctk.CTkLabel(cell, text="", anchor="w", height=16, text_color=theme.TEXT_MUTED,
                                 font=theme.font(theme.FONT_SIZE_SM))
            label.pack(anchor="w")
            self._count_labels[kind] = (number, label)
        self._ignored = ctk.CTkLabel(inner, text="", anchor="w", justify="left", wraplength=_WIDTH - 90,
                                     text_color=theme.TEXT_MUTED, font=theme.font(theme.FONT_SIZE_SM))

    # ------------------------------------------------------------------
    # SHEET AND COLUMNS
    # ------------------------------------------------------------------

    def _choose_file(self) -> None:
        path = filedialog.askopenfilename(
            parent=self, title="Escolha a planilha de entregas", filetypes=[("Planilha do Excel", "*.xlsx")],
        )
        if path:
            self._open_sheet(path, keep_columns=False)
            if self._watcher is not None:  # another sheet: watch it from its current state
                self._start_watching()

    def _on_column_picked(self) -> None:
        self._columns_confirmed = True
        self._save_prefs()

    def _open_sheet(self, path: str, keep_columns: bool) -> None:
        """Reads the header row to fill the column menus. A saved choice is kept only if each column still has
        the title it was chosen by; otherwise the columns are suggested again from the titles. A sheet that
        can't be read leaves the saved choice alone (e.g. a network drive not mounted yet at startup)."""
        self._path.set(path)
        try:
            headers = read_headers(Path(path))
        except FileNotFoundError:
            headers, error = [], f"Planilha não encontrada: {Path(path).name}"
        except SheetError as sheet_error:
            headers, error = [], str(sheet_error)
        except OSError:
            logger.warning("Could not read %s", path, exc_info=True)
            headers, error = [], f"Não foi possível ler a planilha {Path(path).name}."
        else:
            error = ""
        self._show_file_error(error)

        self._options = column_options(headers)
        saved, saved_titles = self._prefs.columns, self._prefs.titles
        self._columns_confirmed = keep_columns and saved_columns_valid(headers, saved, saved_titles)
        chosen = choose_columns(headers, saved, saved_titles, keep=keep_columns)
        by_letter = {letter_of(option): option for option in self._options}
        for field, menu in self._menus.items():
            values = ([NO_COLUMN] if field == "cte" else []) + self._options
            menu.configure(values=values or [_CHOOSE])
            default = NO_COLUMN if field == "cte" else _CHOOSE
            menu.set(by_letter.get(chosen.get(field), default))
        if error and keep_columns:
            return  # nothing was read: keep the saved columns for when the sheet is back
        self._save_prefs()

    def _show_file_error(self, error: str) -> None:
        self._file_error.configure(text=error)
        if error:
            self._file_error.pack(fill="x", pady=(theme.SPACE_XS, 0), before=self._columns_card)
        else:
            self._file_error.pack_forget()

    def _chosen(self) -> dict[str, str | None]:
        return {field: letter_of(menu.get()) if menu.get() in self._options else None
                for field, menu in self._menus.items()}

    def _titles(self) -> dict[str, str]:
        """Header title of each chosen column, checked again by sync() right before reading the rows."""
        return {field: title_of(menu.get()) for field, menu in self._menus.items() if menu.get() in self._options}

    def _save_prefs(self) -> None:
        if self._options and self._columns_confirmed:
            columns, titles = self._chosen(), self._titles()
        else:
            # Keep the last checked choice: the sheet wasn't read (empty menus), or the columns on screen weren't
            # checked yet. Saving them would make them count as checked on the next start.
            columns, titles = self._prefs.columns, self._prefs.titles
        self._prefs = Prefs(path=self._path.get(), columns=columns, titles=titles, auto_send=bool(self._auto.get()))
        try:
            save_prefs(self._prefs)
        except OSError:
            logger.warning("Could not save the preferences", exc_info=True)

    # ------------------------------------------------------------------
    # SENDING
    # ------------------------------------------------------------------

    def _mtime(self) -> float | None:
        try:
            return os.stat(self._path.get()).st_mtime
        except OSError:  # no file chosen, or missing for a moment while Excel saves it
            return None

    def _on_auto_toggle(self) -> None:
        if self._auto.get() and self._options:  # turning it on with the columns in view counts as checking them
            self._columns_confirmed = True
        self._save_prefs()
        if self._auto.get():
            self._start_watching()
        else:
            self._stop_watching()

    def _start_watching(self) -> None:
        """From the sheet as it is now: turning it on doesn't send a save made before."""
        self._stop_watching()
        self._watcher = ChangeWatcher(sent_mtime=self._mtime())
        self._watch_job = self.after(_WATCH_MS, self._watch)

    def _stop_watching(self) -> None:
        if self._watch_job is not None:
            self.after_cancel(self._watch_job)
            self._watch_job = None
        self._watcher = None

    def _watch(self) -> None:
        self._watch_job = None
        if self._watcher is None:
            return
        delay = _WATCH_MS
        if not self._sending:  # a send in progress: look again at the next check
            action = self._watcher.tick(self._mtime())
            if action == "confirm":
                delay = _CONFIRM_MS
            elif action == "send":
                self._auto_send()
        self._watch_job = self.after(delay, self._watch)

    def _auto_send(self) -> None:
        if not self._options:  # the sheet couldn't be read before (e.g. a network drive): read its header now
            self._open_sheet(self._path.get(), keep_columns=True)
        if self._columns_confirmed:
            self._send(auto=True)
            return
        reason = ("A planilha não pôde ser lida." if not self._options
                  else "Confira as colunas da planilha e clique em Enviar agora.")
        self._show_result_card(Tone.WARNING, "Envio automático pausado", message=reason)

    def destroy(self) -> None:
        self._stop_watching()
        super().destroy()

    def _send(self, preview: bool = False, auto: bool = False) -> None:
        if self._sending:
            return
        chosen = self._chosen()
        missing = [_FIELD_LABELS[f] for f in _REQUIRED if not chosen[f]]
        if not self._path.get() or missing:
            text = "Escolha a planilha." if not self._path.get() else f"Escolha a coluna de {', '.join(missing)}."
            self._show_result_card(Tone.ERROR, "Não foi possível enviar", message=text)
            return
        columns = Columns(nfe=chosen["nfe"], driver=chosen["driver"], date=chosen["date"], cte=chosen["cte"])
        path, titles = self._path.get(), self._titles()

        self._sending = True
        self._auto_running = auto
        self._send_watcher = self._watcher if auto else None
        self._btn_preview.configure(state="disabled", text="Conferindo…" if preview else "Conferir sem enviar")
        self._btn_send.configure(state="disabled", text="Enviar agora" if preview else "Enviando…")
        # No other sheet while this one is sent: its result would land on the new sheet's columns
        self._btn_change.configure(state="disabled")

        def work() -> None:
            result = sync(path, columns, self._config, preview=preview, titles=titles)
            self.after(0, self._finish, result)

        threading.Thread(target=work, daemon=True).start()

    def _finish(self, result: SyncResult) -> None:
        self._sending = False
        self._btn_preview.configure(state="normal", text="Conferir sem enviar")
        self._btn_send.configure(state="normal", text="Enviar agora")
        self._btn_change.configure(state="normal")
        if result.columns_changed:
            # Reload the menus from the new header; they stay unconfirmed, so the automatic send waits for
            # the user to check them
            self._open_sheet(self._path.get(), keep_columns=True)
        elif self._auto_running and result.error and self._watcher is not None \
                and self._watcher is self._send_watcher:
            # e.g. no internet: the same save goes again at the next checks. Only on the watcher that started
            # the send: after "Trocar" or a toggle, a new watcher must not send another sheet unasked.
            self._watcher.retry()
        elif not self._auto_running and not result.error and not self._columns_confirmed:
            self._columns_confirmed = True  # a manual send or preview went through with these columns
            self._save_prefs()
        planned = result.new + result.updated
        if result.preview and not result.error:
            message = (f"Ao enviar, {planned} {'linha vai' if planned == 1 else 'linhas vão'} para a tabela."
                       if planned else "Nada mudou desde o último envio.")
            self._show_result_card(Tone.INFO, "Conferência: nada foi enviado", message=message, result=result)
        elif result.error and result.written:
            message = (f"{result.written} de {planned} linhas chegaram à tabela. Envie de novo para terminar.\n"
                       f"{result.error}")
            self._show_result_card(Tone.WARNING, "Envio interrompido", message=message, result=result)
        elif result.error:
            self._show_result_card(Tone.ERROR, "Não foi possível enviar", message=result.error, result=result)
        else:
            when = sent_label(result.finished_at, datetime.now().astimezone())
            message = "" if planned else "Nada mudou desde o último envio."
            if self._auto_running:
                message = " ".join(filter(None, ["Enviado sozinho ao salvar a planilha.", message]))
            self._show_result_card(Tone.OK, f"Último envio: {when}", message=message, result=result)

    def _show_result_card(self, tone: Tone, title: str, message: str = "", result: SyncResult | None = None) -> None:
        strong, background = theme.STATUS[tone.value]
        soft, line, _outline = theme.BANNER[tone.value]
        icon = {Tone.OK: "file-check", Tone.WARNING: "rotate-cw", Tone.INFO: "file-search"}.get(tone, "x")
        self._result.configure(fg_color=background, border_color=line)
        self._result_title.configure(text=f"  {title}", text_color=soft, image=get_icon(icon, 16, strong))
        self._result_message.configure(text=message, text_color=soft)

        for widget in (self._result_message, self._counts, self._ignored):
            widget.pack_forget()
        if message:
            self._result_message.pack(fill="x", pady=(theme.SPACE_XS, 0))
        # Counts only after the sheet and the table were read (an error before that has nothing to count)
        if result is not None and (result.new or result.updated or result.unchanged or result.ignored):
            counts = {"new": result.new, "updated": result.updated, "ignored": len(result.ignored)}
            for kind, value in counts.items():
                number, label = self._count_labels[kind]
                warn = kind == "ignored" and value
                number.configure(text=str(value),
                                 text_color=theme.STATUS[Tone.WARNING.value][0] if warn else theme.TEXT)
                label.configure(text=count_label(kind, value))
            self._counts.pack(fill="x", pady=(theme.SPACE_SM, 0))
        if result is not None and result.ignored:
            self._ignored.configure(text="Ignoradas:\n" + "\n".join(ignored_lines(result.ignored)))
            self._ignored.pack(fill="x", pady=(theme.SPACE_SM, 0))
        if not self._result.winfo_manager():
            self._result.pack(fill="x", pady=theme.SPACE_LG, after=self._columns_card)
        self._fit_height()
