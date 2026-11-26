import os
import threading
from datetime import datetime
from tkinter import filedialog
from typing import Callable

import customtkinter as ctk

from ui import theme
from ui.widgets.buttons import restore_button, show_cancel
from ui.widgets.chip import make_chip
from ui.widgets.history import HistoryPanel
from ui.widgets.progress import make_progress, set_message
from ui.widgets.scrollbar import hide_frame_scrollbar_when_idle
from ui.widgets.table import make_header, insert_row, clear_scroll
from ui.widgets.topbar import make_topbar
from ui.workers.rename import RenameWorker
from ui.workers.upload import UploadWorker
from utils.status import Tone, rename_status

_COLS_R = [("Nº", 50), ("Arquivo original", 280), ("NF-e detectada", 140), ("Status", 150)]
_COLS_U = [("Nº", 50), ("NF-e", 120), ("Status", 180)]


class LegacyUploadFrame(ctk.CTkFrame):
    def __init__(self, parent, session, user_name: str, on_logout, on_back=None, relogin: Callable[[], None] | None = None):
        super().__init__(parent, fg_color="transparent")
        self._session       = session
        self._relogin       = relogin
        self._on_logout     = on_logout
        self._on_back     = on_back
        self._stop_event    = threading.Event()
        self._running       = False
        self._step          = "rename"
        self._cnt_ok = self._cnt_dup = self._cnt_error = 0
        self._rows: list    = []
        self._output_folder = ""
        self._btn_style: dict = {}
        self._build(user_name)

    # ------------------------------------------------------------------
    # LAYOUT
    # ------------------------------------------------------------------

    def _build(self, user_name: str) -> None:
        make_topbar(self, "Upload Canhotos", user_name, self._logout,
                    on_back=self._back if self._on_back else None)
        main = ctk.CTkFrame(self, fg_color="transparent")
        main.pack(fill="both", expand=True, padx=16, pady=12)
        self._build_rename_step(main)
        self.lbl_progress, self.progressbar = make_progress(main)
        self._build_table(main)
        self._build_footer(main)
        self._build_history(main)

    def _build_rename_step(self, main: ctk.CTkFrame) -> None:
        row = ctk.CTkFrame(main, fg_color="transparent")
        row.pack(fill="x", pady=(0, 8))

        ctk.CTkLabel(row, text="Pasta de imagens:").pack(side="left", padx=(0, 6))
        self.entry_input_folder = ctk.CTkEntry(row, width=320, placeholder_text="imagens")
        self.entry_input_folder.pack(side="left", padx=(0, 4))
        ctk.CTkButton(
            row, text="...", width=34,
            fg_color="transparent", hover_color=theme.SURFACE_2, border_width=1, border_color=theme.BORDER_INPUT,
            command=self._select_input_folder,
        ).pack(side="left", padx=(0, 8))

        self.btn_rename = ctk.CTkButton(row, text="Renomear", width=120, command=self._start_rename)
        self.btn_rename.pack(side="left", padx=(0, 6))

        ctk.CTkButton(
            row, text="Limpar", width=80,
            fg_color="transparent", hover_color=theme.SURFACE_2,
            border_width=1, border_color=theme.BORDER_INPUT,
            command=self._clear_rename,
        ).pack(side="left")

        self.entry_input_folder.bind("<Return>", lambda e: self._start_rename())
        self.entry_input_folder.bind("<Tab>", lambda e: (self._start_rename(), "break"))

    def _build_table(self, main: ctk.CTkFrame) -> None:
        hdr_slot = ctk.CTkFrame(main, fg_color="transparent")
        hdr_slot.pack(fill="x")
        self.hdr_rename = make_header(hdr_slot, _COLS_R)
        self.hdr_rename.pack(fill="x")
        self.hdr_upload = make_header(hdr_slot, _COLS_U)
        self.scroll = ctk.CTkScrollableFrame(main)
        self.scroll.pack(fill="both", expand=True, pady=(2, 6))
        hide_frame_scrollbar_when_idle(self.scroll)
        self._row_count = 0

    def _build_footer(self, main: ctk.CTkFrame) -> None:
        bar = ctk.CTkFrame(main, fg_color="transparent")
        bar.pack(fill="x", pady=(4, 0))

        stat = ctk.CTkFrame(bar, fg_color="transparent")
        stat.pack(side="left")
        self.chip_ok    = make_chip(stat, Tone.OK)
        self.chip_dup   = make_chip(stat, Tone.WARNING)
        self.chip_error = make_chip(stat, Tone.ERROR)
        self._reset_rename_chips()

        self._frame_upload_bar = ctk.CTkFrame(bar, fg_color="transparent")

        ctk.CTkLabel(self._frame_upload_bar, text="Data de entrega:").pack(side="left", padx=(0, 6))
        self.entry_date = ctk.CTkEntry(
            self._frame_upload_bar, width=115, placeholder_text="DD/MM/AAAA",
        )
        self.entry_date.pack(side="left", padx=(0, 10))
        self.entry_date.bind("<KeyRelease>", self._on_data_keyrelease)

        self.btn_upload = ctk.CTkButton(
            self._frame_upload_bar, text="Iniciar Upload", width=125,
            command=self._start_upload,
        )
        self.btn_upload.pack(side="left")
        self._frame_upload_bar.pack(side="right")

    def _build_history(self, main: ctk.CTkFrame) -> None:
        self._hist = HistoryPanel(main, on_restore=self._restore)

    # ------------------------------------------------------------------
    # HELPERS VISUAIS
    # ------------------------------------------------------------------

    def _reset_rename_chips(self) -> None:
        self._cnt_ok = self._cnt_dup = self._cnt_error = 0
        self._update_rename_chips()

    def _reset_upload_chips(self) -> None:
        self._cnt_ok = self._cnt_dup = self._cnt_error = 0
        self._update_upload_chips()

    def _update_rename_chips(self) -> None:
        self.chip_ok.configure(text=f"{self._cnt_ok}  Renomeadas")
        self.chip_dup.configure(text=f"{self._cnt_dup}  Duplicatas")
        self.chip_error.configure(text=f"{self._cnt_error}  Não lidas")

    def _update_upload_chips(self) -> None:
        self.chip_ok.configure(text=f"{self._cnt_ok}  Enviados")
        self.chip_dup.configure(text=f"{self._cnt_dup}  Ignorados")
        self.chip_error.configure(text=f"{self._cnt_error}  Erros")

    def _on_data_keyrelease(self, event=None) -> None:
        if event and event.keysym == "BackSpace":
            val = self.entry_date.get()
            if val.endswith("/"):
                self.entry_date.delete(len(val) - 1)
            return
        if event and event.keysym in ("Delete", "Left", "Right", "Tab", "Return", "Shift_L", "Shift_R", "Control_L", "Control_R"):
            return
        val = self.entry_date.get()
        digits = "".join(c for c in val if c.isdigit())[:8]
        if len(digits) >= 5:
            formatted = f"{digits[:2]}/{digits[2:4]}/{digits[4:]}"
        elif len(digits) >= 3:
            formatted = f"{digits[:2]}/{digits[2:]}"
        else:
            formatted = digits
        if formatted != val:
            self.entry_date.delete(0, "end")
            self.entry_date.insert(0, formatted)
            self.entry_date.icursor(len(formatted))

    def _clear_rename(self) -> None:
        self.entry_input_folder.delete(0, "end")
        self.entry_date.delete(0, "end")
        self._output_folder = ""
        self.hdr_upload.pack_forget()
        self.hdr_rename.pack(fill="x")
        self._clear_table()
        set_message(self.lbl_progress, "")
        self.progressbar.set(0)
        self._reset_rename_chips()

    def _clear_table(self) -> None:
        clear_scroll(self.scroll)
        self._row_count = 0

    def _insert_rename_row(self, filename: str, invoice_num: str | None, status: str) -> None:
        self._row_count += 1
        label, tone = rename_status(status)
        insert_row(self.scroll, self._row_count, _COLS_R,
                   [str(self._row_count), filename, invoice_num or "-"], label, tone)
        self._rows.append((filename, invoice_num, status))
        if status == "ok":
            self._cnt_ok += 1
        elif status == "duplicata":
            self._cnt_dup += 1
        else:
            self._cnt_error += 1
        self._update_rename_chips()

    def _insert_upload_row(self, invoice_num: str, tone: Tone, text: str) -> None:
        self._row_count += 1
        insert_row(self.scroll, self._row_count, _COLS_U, [str(self._row_count), invoice_num], text, tone)
        self._rows.append((invoice_num, tone, text))
        if tone is Tone.OK:
            self._cnt_ok += 1
        elif tone is Tone.WARNING:
            self._cnt_dup += 1
        else:
            self._cnt_error += 1
        self._update_upload_chips()

    # ------------------------------------------------------------------
    # SELETORES DE PASTA
    # ------------------------------------------------------------------

    def _select_input_folder(self) -> None:
        folder = filedialog.askdirectory(title="Selecionar pasta de imagens")
        if folder:
            self.entry_input_folder.delete(0, "end")
            self.entry_input_folder.insert(0, folder)

    # ------------------------------------------------------------------
    # ETAPA 1 — RENOMEAR
    # ------------------------------------------------------------------

    def _start_rename(self) -> None:
        if self._running:
            return
        folder = self.entry_input_folder.get().strip() or "images"
        if not os.path.isdir(folder):
            set_message(self.lbl_progress, f"Pasta não encontrada: {folder}", Tone.WARNING)
            return

        self._step = "rename"
        self._rows = []
        self.hdr_upload.pack_forget()
        self.hdr_rename.pack(fill="x")
        self._clear_table()
        self._reset_rename_chips()
        set_message(self.lbl_progress, "")
        self.progressbar.set(0)
        self._running = True
        self._stop_event.clear()
        self._btn_style = show_cancel(self.btn_rename, self._cancel)
        worker = RenameWorker(
            folder=folder,
            stop_event=self._stop_event,
            after_fn=self.after,
            on_update=self._update_rename,
            on_done=lambda output: self._finish_rename(cancelled=False, output=output),
            on_cancel=lambda: self._finish_rename(cancelled=True),
        )
        threading.Thread(target=worker.run, daemon=True).start()

    def _update_rename(self, filename: str, invoice_num: str | None, status: str, prog: float, current: int, total: int, elapsed: float) -> None:
        self.progressbar.set(prog)
        m, s = divmod(int(elapsed), 60)
        set_message(self.lbl_progress, f"{filename}  ({current}/{total})  {m:02d}:{s:02d}")
        self._insert_rename_row(filename, invoice_num, status)

    def _finish_rename(self, cancelled: bool, output: str = "") -> None:
        self._running = False
        restore_button(self.btn_rename, self._btn_style)
        if cancelled:
            set_message(self.lbl_progress, "Renomeação cancelada.")
            return

        self.progressbar.set(1)
        set_message(self.lbl_progress, "Renomeação concluída.")
        self._output_folder = output
        self._add_history(
            entry_type="rename",
            label=(f"{self._cnt_ok} renomeadas  ·  {self._cnt_dup} duplicatas  ·  "
                   f"{self._cnt_error} não lidas  —  {output}"),
            folder=output,
            date_str="",
            rows=list(self._rows),
        )

    # ------------------------------------------------------------------
    # ETAPA 2 — UPLOAD
    # ------------------------------------------------------------------

    def _start_upload(self) -> None:
        if self._running:
            return
        if self._output_folder and os.path.isdir(str(self._output_folder)):
            folder = str(self._output_folder)
        else:
            raw = self.entry_input_folder.get().strip()
            candidate = os.path.join(raw, "renomeadas") if raw else ""
            if candidate and os.path.isdir(candidate):
                folder = candidate
            elif raw and os.path.isdir(raw):
                folder = raw
            else:
                folder = "renomeadas"
        if not os.path.isdir(folder):
            set_message(self.lbl_progress, f"Pasta não encontrada: {folder}", Tone.WARNING)
            return

        date_str = self.entry_date.get().strip()
        try:
            dt = datetime.strptime(date_str, "%d/%m/%Y")
            batch_date = dt.strftime("%Y-%m-%dT12:00:00.000Z")
        except ValueError:
            set_message(self.lbl_progress, "Data inválida. Use DD/MM/AAAA.", Tone.WARNING)
            return

        self._step = "upload"
        self._rows = []
        self.hdr_rename.pack_forget()
        self.hdr_upload.pack(fill="x")
        self._clear_table()
        self._reset_upload_chips()
        set_message(self.lbl_progress, "")
        self.progressbar.set(0)
        self._running = True
        self._stop_event.clear()
        self._btn_style = show_cancel(self.btn_upload, self._cancel)
        worker = UploadWorker(
            session=self._session,
            folder=folder,
            batch_date=batch_date,
            stop_event=self._stop_event,
            after_fn=self.after,
            on_update=self._update_upload,
            on_done=lambda: self._finish_upload(cancelled=False, folder=folder, date_str=date_str),
            on_cancel=lambda: self._finish_upload(cancelled=True),
            on_session_lost=lambda: self._finish_upload(cancelled=True, session_lost=True),
            relogin=self._relogin,
        )
        threading.Thread(target=worker.run, daemon=True).start()

    def _update_upload(
        self, invoice_num: str, tone: Tone, text: str, prog: float, current: int, total: int, elapsed: float,
    ) -> None:
        self.progressbar.set(prog)
        m, s = divmod(int(elapsed), 60)
        set_message(self.lbl_progress, f"NF-e {invoice_num}  ({current}/{total})  {m:02d}:{s:02d}")
        self._insert_upload_row(invoice_num, tone, text)

    def _finish_upload(
        self, cancelled: bool, folder: str = "", date_str: str = "", session_lost: bool = False,
    ) -> None:
        self._running = False
        restore_button(self.btn_upload, self._btn_style)
        if session_lost:
            set_message(self.lbl_progress, "Sessão expirada. Saia e entre de novo.", Tone.ERROR)
        elif cancelled:
            set_message(self.lbl_progress, "Upload cancelado.")
        else:
            self.progressbar.set(1)
            failures = sum(1 for _, tone, _ in self._rows if tone is Tone.CONNECTION)
            if failures:
                # Those files stayed in the folder; running the upload again sends only them.
                set_message(
                    self.lbl_progress,
                    f"Upload concluído com {failures} falha(s) de conexão. Inicie o upload de novo para enviar essas.",
                    Tone.CONNECTION,
                )
            else:
                set_message(self.lbl_progress, "Upload concluído.")
            self._add_history(
                entry_type="upload",
                label=(f"{self._cnt_ok} enviados  ·  {self._cnt_dup} ignorados  ·  "
                       f"{self._cnt_error} erros  —  {folder}  ·  {date_str}"),
                folder=folder,
                date_str=date_str,
                rows=list(self._rows),
            )

    # ------------------------------------------------------------------
    # HISTÓRICO
    # ------------------------------------------------------------------

    def _add_history(self, entry_type: str, label: str, folder: str, date_str: str, rows: list) -> None:
        hour = datetime.now().strftime("%H:%M")
        self._hist.add({
            "type": entry_type, "label": f"{hour}  ·  {label}",
            "folder": folder, "date_str": date_str, "rows": rows,
        })

    def _restore(self, entry: dict) -> None:
        if self._running:
            return
        self._clear_table()
        if entry["type"] == "rename":
            self._reset_rename_chips()
            self.hdr_upload.pack_forget()
            self.hdr_rename.pack(fill="x")
            for filename, invoice_num, status in entry["rows"]:
                self._insert_rename_row(filename, invoice_num, status)
            self.entry_input_folder.delete(0, "end")
            self.entry_input_folder.insert(0, entry["folder"])
        else:
            self._reset_upload_chips()
            self.hdr_rename.pack_forget()
            self.hdr_upload.pack(fill="x")
            for invoice_num, tone, text in entry["rows"]:
                self._insert_upload_row(invoice_num, tone, text)
            self._output_folder = entry["folder"]
            self.entry_date.delete(0, "end")
            self.entry_date.insert(0, entry["date_str"])
        self.scroll._parent_canvas.yview_moveto(0)
        set_message(self.lbl_progress, f"Histórico: {entry['label']}")
        self.progressbar.set(1)

    # ------------------------------------------------------------------
    # CANCELAR / SAIR
    # ------------------------------------------------------------------

    def _cancel(self) -> None:
        self._stop_event.set()

    def _back(self) -> None:
        self._stop_event.set()
        self._on_back()

    def _logout(self) -> None:
        self._stop_event.set()
        self._on_logout()
