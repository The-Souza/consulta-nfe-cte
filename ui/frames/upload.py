import os
import threading
from datetime import datetime
from tkinter import filedialog

import customtkinter as ctk

from ui.widgets.chip import make_chip
from ui.widgets.history import HistoryPanel
from ui.widgets.progress import make_progress
from ui.widgets.table import make_header, insert_row, clear_scroll
from ui.widgets.topbar import make_topbar
from ui.workers.rename import RenameWorker
from ui.workers.upload import UploadWorker

_COLS_R = [("Nº", 50), ("Arquivo original", 280), ("NF-e detectada", 140), ("Status", 150)]
_COLS_U = [("Nº", 50), ("NF-e", 120), ("Status", 180)]


class UploadFrame(ctk.CTkFrame):
    def __init__(self, parent, session, user_name: str, on_logout, on_back=None):
        super().__init__(parent, fg_color="transparent")
        self._session       = session
        self._on_logout     = on_logout
        self._on_back     = on_back
        self._stop_event    = threading.Event()
        self._running       = False
        self._step          = "rename"
        self._cnt_ok = self._cnt_dup = self._cnt_error = 0
        self._rows: list    = []
        self._output_folder = ""
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
            fg_color="transparent", border_width=1, border_color="gray",
            command=self._select_input_folder,
        ).pack(side="left", padx=(0, 8))

        self.btn_rename = ctk.CTkButton(row, text="Renomear", width=120, command=self._start_rename)
        self.btn_rename.pack(side="left", padx=(0, 6))
        self._btn_rename_fg    = self.btn_rename.cget("fg_color")
        self._btn_rename_hover = self.btn_rename.cget("hover_color")

        ctk.CTkButton(
            row, text="Limpar", width=80,
            fg_color="transparent", hover_color="#444",
            border_width=1, border_color="gray",
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
        self._row_count = 0

    def _build_footer(self, main: ctk.CTkFrame) -> None:
        bar = ctk.CTkFrame(main, fg_color="transparent")
        bar.pack(fill="x", pady=(4, 0))

        stat = ctk.CTkFrame(bar, fg_color="transparent")
        stat.pack(side="left")
        self.chip_ok    = make_chip(stat, "#4CAF50", "#1a3a1a")
        self.chip_dup   = make_chip(stat, "#FFC107", "#3a3000")
        self.chip_error = make_chip(stat, "#F44336", "#3a0f0f")
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
        self._btn_upload_fg    = self.btn_upload.cget("fg_color")
        self._btn_upload_hover = self.btn_upload.cget("hover_color")
        self._frame_upload_bar.pack(side="right")

    def _build_history(self, main: ctk.CTkFrame) -> None:
        self._hist = HistoryPanel(main, on_restore=self._restore)

    # ------------------------------------------------------------------
    # HELPERS VISUAIS
    # ------------------------------------------------------------------

    def _reset_rename_chips(self) -> None:
        self._cnt_ok = self._cnt_dup = self._cnt_error = 0
        self.chip_ok.configure(text="✅  0  Renomeadas")
        self.chip_dup.configure(text="⚠  0  Duplicatas")
        self.chip_error.configure(text="❌  0  Não lidas")

    def _reset_upload_chips(self) -> None:
        self._cnt_ok = self._cnt_dup = self._cnt_error = 0
        self.chip_ok.configure(text="✅  0  Enviados")
        self.chip_dup.configure(text="⚠  0  Ignorados")
        self.chip_error.configure(text="❌  0  Erros")

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
        self.lbl_progress.configure(text="")
        self.progressbar.set(0)
        self._reset_rename_chips()

    def _clear_table(self) -> None:
        clear_scroll(self.scroll)
        self._row_count = 0

    def _insert_rename_row(self, filename: str, invoice_num: str | None, status: str) -> None:
        self._row_count += 1
        _COR = {
            "ok":             ("✅ Renomeada", "#4CAF50", "#1a3a1a"),
            "duplicata":      ("⚠ Duplicata",  "#FFC107", "#3a3000"),
            "nao_encontrada": ("❌ Não lida",  "#F44336", "#3a0f0f"),
            "erro":           ("❌ Erro",       "#F44336", "#3a0f0f"),
        }
        label, text_color, bg_color = _COR.get(status, ("❌ Erro", "#F44336", "#3a0f0f"))
        insert_row(self.scroll, self._row_count, _COLS_R,
                   [str(self._row_count), filename, invoice_num or "-"], label, text_color, bg_color)
        self._rows.append((filename, invoice_num, status))
        if status == "ok":
            self._cnt_ok += 1
        elif status == "duplicata":
            self._cnt_dup += 1
        else:
            self._cnt_error += 1
        self.chip_ok.configure(text=f"✅  {self._cnt_ok}  Renomeadas")
        self.chip_dup.configure(text=f"⚠  {self._cnt_dup}  Duplicatas")
        self.chip_error.configure(text=f"❌  {self._cnt_error}  Não lidas")

    def _insert_upload_row(self, invoice_num: str, status: str) -> None:
        self._row_count += 1
        _COR = {"✅": ("#4CAF50", "#1a3a1a"), "⚠": ("#FFC107", "#3a3000"), "❌": ("#F44336", "#3a0f0f")}
        text_color, bg_color = next(((f, b) for k, (f, b) in _COR.items() if k in status), ("#aaa", "transparent"))
        insert_row(self.scroll, self._row_count, _COLS_U,
                   [str(self._row_count), invoice_num], status, text_color, bg_color)
        self._rows.append((invoice_num, status))
        if "✅" in status:
            self._cnt_ok += 1
        elif "⚠" in status:
            self._cnt_dup += 1
        else:
            self._cnt_error += 1
        self.chip_ok.configure(text=f"✅  {self._cnt_ok}  Enviados")
        self.chip_dup.configure(text=f"⚠  {self._cnt_dup}  Ignorados")
        self.chip_error.configure(text=f"❌  {self._cnt_error}  Erros")

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
            self.lbl_progress.configure(text=f"⚠ Pasta não encontrada: {folder}")
            return

        self._step = "rename"
        self._rows = []
        self.hdr_upload.pack_forget()
        self.hdr_rename.pack(fill="x")
        self._clear_table()
        self._reset_rename_chips()
        self.progressbar.set(0)
        self._running = True
        self._stop_event.clear()
        self.btn_rename.configure(
            text="⏹ Cancelar",
            fg_color=("#c0392b", "#7b241c"), hover_color=("#a93226", "#641e16"),
            command=self._cancel,
        )
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
        self.lbl_progress.configure(text=f"{filename}  ({current}/{total})  {m:02d}:{s:02d}")
        self._insert_rename_row(filename, invoice_num, status)

    def _finish_rename(self, cancelled: bool, output: str = "") -> None:
        self._running = False
        self.btn_rename.configure(
            text="Renomear",
            fg_color=self._btn_rename_fg, hover_color=self._btn_rename_hover,
            command=self._start_rename,
        )
        if cancelled:
            self.lbl_progress.configure(text="Renomeação cancelada.")
            return

        self.progressbar.set(1)
        self.lbl_progress.configure(text="Renomeação concluída.")
        self._output_folder = output
        self._add_history(
            entry_type="rename",
            label=f"✅ {self._cnt_ok}  ·  ⚠ {self._cnt_dup}  ·  ❌ {self._cnt_error}  —  {output}",
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
            self.lbl_progress.configure(text=f"⚠ Pasta não encontrada: {folder}")
            return

        date_str = self.entry_date.get().strip()
        try:
            dt = datetime.strptime(date_str, "%d/%m/%Y")
            batch_date = dt.strftime("%Y-%m-%dT12:00:00.000Z")
        except ValueError:
            self.lbl_progress.configure(text="⚠ Data inválida. Use DD/MM/AAAA.")
            return

        self._step = "upload"
        self._rows = []
        self.hdr_rename.pack_forget()
        self.hdr_upload.pack(fill="x")
        self._clear_table()
        self._reset_upload_chips()
        self.progressbar.set(0)
        self._running = True
        self._stop_event.clear()
        self.btn_upload.configure(
            text="⏹ Cancelar",
            fg_color=("#c0392b", "#7b241c"), hover_color=("#a93226", "#641e16"),
            command=self._cancel,
        )
        worker = UploadWorker(
            session=self._session,
            folder=folder,
            batch_date=batch_date,
            stop_event=self._stop_event,
            after_fn=self.after,
            on_update=self._update_upload,
            on_done=lambda: self._finish_upload(cancelled=False, folder=folder, date_str=date_str),
            on_cancel=lambda: self._finish_upload(cancelled=True),
        )
        threading.Thread(target=worker.run, daemon=True).start()

    def _update_upload(self, invoice_num: str, status: str, prog: float, current: int, total: int, elapsed: float) -> None:
        self.progressbar.set(prog)
        m, s = divmod(int(elapsed), 60)
        self.lbl_progress.configure(text=f"NF-e {invoice_num}  ({current}/{total})  {m:02d}:{s:02d}")
        self._insert_upload_row(invoice_num, status)

    def _finish_upload(self, cancelled: bool, folder: str = "", date_str: str = "") -> None:
        self._running = False
        self.btn_upload.configure(
            text="Iniciar Upload",
            fg_color=self._btn_upload_fg, hover_color=self._btn_upload_hover,
            command=self._start_upload,
        )
        if cancelled:
            self.lbl_progress.configure(text="Upload cancelado.")
        else:
            self.progressbar.set(1)
            self.lbl_progress.configure(text="Upload concluído.")
            self._add_history(
                entry_type="upload",
                label=f"✅ {self._cnt_ok}  ·  ⚠ {self._cnt_dup}  ·  ❌ {self._cnt_error}  —  {folder}  ·  {date_str}",
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
            for invoice_num, status in entry["rows"]:
                self._insert_upload_row(invoice_num, status)
            self._output_folder = entry["folder"]
            self.entry_date.delete(0, "end")
            self.entry_date.insert(0, entry["date_str"])
        self.scroll._parent_canvas.yview_moveto(0)
        self.lbl_progress.configure(text=f"Histórico: {entry['label']}")
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
