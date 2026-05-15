import os
import threading
from datetime import datetime
from tkinter import filedialog

import customtkinter as ctk

from ui.widgets.chip import fazer_chip
from ui.widgets.historico import PainelHistorico
from ui.widgets.progresso import fazer_progresso
from ui.widgets.tabela import fazer_cabecalho, inserir_linha, limpar_scroll
from ui.widgets.topbar import fazer_topbar
from ui.workers.renomear import RenomearWorker
from ui.workers.upload import UploadWorker

_COLS_R = [("Nº", 50), ("Arquivo original", 280), ("NF-e detectada", 140), ("Status", 150)]
_COLS_U = [("Nº", 50), ("NF-e", 120), ("Status", 180)]


class UploadFrame(ctk.CTkFrame):
    def __init__(self, parent, session, usuario_nome: str, on_logout):
        super().__init__(parent, fg_color="transparent")
        self._session    = session
        self._on_logout  = on_logout
        self._stop_event = threading.Event()
        self._rodando    = False
        self._etapa      = "renomear"
        self._cnt_ok = self._cnt_dup = self._cnt_nao = 0
        self._rows: list = []
        self._pasta_output = ""
        self._build(usuario_nome)

    # ------------------------------------------------------------------
    # LAYOUT
    # ------------------------------------------------------------------

    def _build(self, usuario_nome: str) -> None:
        fazer_topbar(self, "Upload Canhotos", usuario_nome, self._sair)
        main = ctk.CTkFrame(self, fg_color="transparent")
        main.pack(fill="both", expand=True, padx=16, pady=12)
        self._build_etapa_renomear(main)
        self.lbl_progresso, self.progressbar = fazer_progresso(main)
        self._build_tabela(main)
        self._build_rodape(main)
        self._build_historico(main)

    def _build_etapa_renomear(self, main: ctk.CTkFrame) -> None:
        row = ctk.CTkFrame(main, fg_color="transparent")
        row.pack(fill="x", pady=(0, 8))

        ctk.CTkLabel(row, text="Pasta de imagens:").pack(side="left", padx=(0, 6))
        self.entry_pasta_input = ctk.CTkEntry(row, width=320, placeholder_text="images_raw")
        self.entry_pasta_input.pack(side="left", padx=(0, 4))
        ctk.CTkButton(
            row, text="...", width=34,
            fg_color="transparent", border_width=1, border_color="gray",
            command=self._selecionar_pasta_input,
        ).pack(side="left", padx=(0, 8))

        self.btn_renomear = ctk.CTkButton(row, text="Renomear", width=120, command=self._iniciar_renomear)
        self.btn_renomear.pack(side="left", padx=(0, 6))
        self._btn_renomear_fg    = self.btn_renomear.cget("fg_color")
        self._btn_renomear_hover = self.btn_renomear.cget("hover_color")

        ctk.CTkButton(
            row, text="Limpar", width=80,
            fg_color="transparent", hover_color="#444",
            border_width=1, border_color="gray",
            command=self._limpar_renomear,
        ).pack(side="left")

        self.entry_pasta_input.bind("<Return>", lambda e: self._iniciar_renomear())
        self.entry_pasta_input.bind("<Tab>", lambda e: (self._iniciar_renomear(), "break"))

    def _build_tabela(self, main: ctk.CTkFrame) -> None:
        hdr_slot = ctk.CTkFrame(main, fg_color="transparent")
        hdr_slot.pack(fill="x")
        self.hdr_renomear = fazer_cabecalho(hdr_slot, _COLS_R)
        self.hdr_renomear.pack(fill="x")
        self.hdr_upload = fazer_cabecalho(hdr_slot, _COLS_U)
        self.scroll = ctk.CTkScrollableFrame(main)
        self.scroll.pack(fill="both", expand=True, pady=(2, 6))
        self._row_count = 0

    def _build_rodape(self, main: ctk.CTkFrame) -> None:
        bar = ctk.CTkFrame(main, fg_color="transparent")
        bar.pack(fill="x", pady=(4, 0))

        stat = ctk.CTkFrame(bar, fg_color="transparent")
        stat.pack(side="left")
        self.chip_ok  = fazer_chip(stat, "#4CAF50", "#1a3a1a")
        self.chip_dup = fazer_chip(stat, "#FFC107", "#3a3000")
        self.chip_nao = fazer_chip(stat, "#F44336", "#3a0f0f")
        self._reset_chips_renomear()

        self._frame_upload_bar = ctk.CTkFrame(bar, fg_color="transparent")

        ctk.CTkLabel(self._frame_upload_bar, text="Data de entrega:").pack(side="left", padx=(0, 6))
        self.entry_data = ctk.CTkEntry(
            self._frame_upload_bar, width=115, placeholder_text="DD/MM/AAAA",
        )
        self.entry_data.pack(side="left", padx=(0, 10))

        self.btn_upload = ctk.CTkButton(
            self._frame_upload_bar, text="Iniciar Upload", width=125,
            command=self._iniciar_upload,
        )
        self.btn_upload.pack(side="left")
        self._btn_upload_fg    = self.btn_upload.cget("fg_color")
        self._btn_upload_hover = self.btn_upload.cget("hover_color")

    def _build_historico(self, main: ctk.CTkFrame) -> None:
        self._hist = PainelHistorico(main, on_restaurar=self._restaurar)

    # ------------------------------------------------------------------
    # HELPERS VISUAIS
    # ------------------------------------------------------------------

    def _reset_chips_renomear(self) -> None:
        self._cnt_ok = self._cnt_dup = self._cnt_nao = 0
        self.chip_ok.configure(text="✅  0  Renomeadas")
        self.chip_dup.configure(text="⚠  0  Duplicatas")
        self.chip_nao.configure(text="❌  0  Não lidas")

    def _reset_chips_upload(self) -> None:
        self._cnt_ok = self._cnt_dup = self._cnt_nao = 0
        self.chip_ok.configure(text="✅  0  Enviados")
        self.chip_dup.configure(text="⚠  0  Ignorados")
        self.chip_nao.configure(text="❌  0  Erros")

    def _limpar_renomear(self) -> None:
        self.entry_pasta_input.delete(0, "end")
        self._frame_upload_bar.pack_forget()
        self.hdr_upload.pack_forget()
        self.hdr_renomear.pack(fill="x")
        self._limpar_tabela()
        self.lbl_progresso.configure(text="")
        self.progressbar.set(0)
        self._reset_chips_renomear()

    def _limpar_tabela(self) -> None:
        limpar_scroll(self.scroll)
        self._row_count = 0

    def _inserir_linha_renomear(self, arquivo: str, nfe: str | None, status: str) -> None:
        self._row_count += 1
        _COR = {
            "ok":             ("✅ Renomeada", "#4CAF50", "#1a3a1a"),
            "duplicata":      ("⚠ Duplicata",  "#FFC107", "#3a3000"),
            "nao_encontrada": ("❌ Não lida",  "#F44336", "#3a0f0f"),
            "erro":           ("❌ Erro",       "#F44336", "#3a0f0f"),
        }
        label, cor_fg, cor_bg = _COR.get(status, ("❌ Erro", "#F44336", "#3a0f0f"))
        inserir_linha(self.scroll, self._row_count, _COLS_R,
                      [str(self._row_count), arquivo, nfe or "-"], label, cor_fg, cor_bg)
        self._rows.append((arquivo, nfe, status))
        if status == "ok":
            self._cnt_ok += 1
        elif status == "duplicata":
            self._cnt_dup += 1
        else:
            self._cnt_nao += 1
        self.chip_ok.configure(text=f"✅  {self._cnt_ok}  Renomeadas")
        self.chip_dup.configure(text=f"⚠  {self._cnt_dup}  Duplicatas")
        self.chip_nao.configure(text=f"❌  {self._cnt_nao}  Não lidas")

    def _inserir_linha_upload(self, nfe: str, status: str) -> None:
        self._row_count += 1
        _COR = {"✅": ("#4CAF50", "#1a3a1a"), "⚠": ("#FFC107", "#3a3000"), "❌": ("#F44336", "#3a0f0f")}
        cor_fg, cor_bg = next(((f, b) for k, (f, b) in _COR.items() if k in status), ("#aaa", "transparent"))
        inserir_linha(self.scroll, self._row_count, _COLS_U,
                      [str(self._row_count), nfe], status, cor_fg, cor_bg)
        self._rows.append((nfe, status))
        if "✅" in status:
            self._cnt_ok += 1
        elif "⚠" in status:
            self._cnt_dup += 1
        else:
            self._cnt_nao += 1
        self.chip_ok.configure(text=f"✅  {self._cnt_ok}  Enviados")
        self.chip_dup.configure(text=f"⚠  {self._cnt_dup}  Ignorados")
        self.chip_nao.configure(text=f"❌  {self._cnt_nao}  Erros")

    # ------------------------------------------------------------------
    # SELETORES DE PASTA
    # ------------------------------------------------------------------

    def _selecionar_pasta_input(self) -> None:
        pasta = filedialog.askdirectory(title="Selecionar pasta de imagens")
        if pasta:
            self.entry_pasta_input.delete(0, "end")
            self.entry_pasta_input.insert(0, pasta)

    # ------------------------------------------------------------------
    # ETAPA 1 — RENOMEAR
    # ------------------------------------------------------------------

    def _iniciar_renomear(self) -> None:
        if self._rodando:
            return
        pasta = self.entry_pasta_input.get().strip() or "images_raw"
        if not os.path.isdir(pasta):
            self.lbl_progresso.configure(text=f"⚠ Pasta não encontrada: {pasta}")
            return

        self._etapa = "renomear"
        self._rows = []
        self._frame_upload_bar.pack_forget()
        self.hdr_upload.pack_forget()
        self.hdr_renomear.pack(fill="x")
        self._limpar_tabela()
        self._reset_chips_renomear()
        self.progressbar.set(0)
        self._rodando = True
        self._stop_event.clear()
        self.btn_renomear.configure(
            text="⏹ Cancelar",
            fg_color=("#c0392b", "#7b241c"), hover_color=("#a93226", "#641e16"),
            command=self._cancelar,
        )
        worker = RenomearWorker(
            pasta=pasta,
            stop_event=self._stop_event,
            after_fn=self.after,
            on_update=self._atualizar_renomear,
            on_done=lambda output: self._finalizar_renomear(cancelado=False, output=output),
            on_cancel=lambda: self._finalizar_renomear(cancelado=True),
        )
        threading.Thread(target=worker.run, daemon=True).start()

    def _atualizar_renomear(self, arquivo: str, nfe: str | None, status: str, prog: float, atual: int, total: int, elapsed: float) -> None:
        self.progressbar.set(prog)
        m, s = divmod(int(elapsed), 60)
        self.lbl_progresso.configure(text=f"{arquivo}  ({atual}/{total})  {m:02d}:{s:02d}")
        self._inserir_linha_renomear(arquivo, nfe, status)

    def _finalizar_renomear(self, cancelado: bool, output: str = "") -> None:
        self._rodando = False
        self.btn_renomear.configure(
            text="Renomear",
            fg_color=self._btn_renomear_fg, hover_color=self._btn_renomear_hover,
            command=self._iniciar_renomear,
        )
        if cancelado:
            self.lbl_progresso.configure(text="Renomeação cancelada.")
            return

        self.progressbar.set(1)
        self.lbl_progresso.configure(text="Renomeação concluída.")
        self._pasta_output = output
        self._frame_upload_bar.pack(side="right")
        self._add_historico(
            tipo="renomear",
            label=f"✅ {self._cnt_ok}  ·  ⚠ {self._cnt_dup}  ·  ❌ {self._cnt_nao}  —  {output}",
            pasta=output,
            data_str="",
            rows=list(self._rows),
        )

    # ------------------------------------------------------------------
    # ETAPA 2 — UPLOAD
    # ------------------------------------------------------------------

    def _iniciar_upload(self) -> None:
        if self._rodando:
            return
        pasta = str(self._pasta_output) or "renamed"
        if not os.path.isdir(pasta):
            self.lbl_progresso.configure(text=f"⚠ Pasta não encontrada: {pasta}")
            return

        data_str = self.entry_data.get().strip()
        try:
            dt = datetime.strptime(data_str, "%d/%m/%Y")
            data_lote = dt.strftime("%Y-%m-%dT12:00:00.000Z")
        except ValueError:
            self.lbl_progresso.configure(text="⚠ Data inválida. Use DD/MM/AAAA.")
            return

        self._etapa = "upload"
        self._rows = []
        self.hdr_renomear.pack_forget()
        self.hdr_upload.pack(fill="x")
        self._limpar_tabela()
        self._reset_chips_upload()
        self.progressbar.set(0)
        self._rodando = True
        self._stop_event.clear()
        self.btn_upload.configure(
            text="⏹ Cancelar",
            fg_color=("#c0392b", "#7b241c"), hover_color=("#a93226", "#641e16"),
            command=self._cancelar,
        )
        worker = UploadWorker(
            session=self._session,
            pasta=pasta,
            data_lote=data_lote,
            stop_event=self._stop_event,
            after_fn=self.after,
            on_update=self._atualizar_upload,
            on_done=lambda: self._finalizar_upload(cancelado=False, pasta=pasta, data_str=data_str),
            on_cancel=lambda: self._finalizar_upload(cancelado=True),
        )
        threading.Thread(target=worker.run, daemon=True).start()

    def _atualizar_upload(self, nfe: str, status: str, prog: float, atual: int, total: int, elapsed: float) -> None:
        self.progressbar.set(prog)
        m, s = divmod(int(elapsed), 60)
        self.lbl_progresso.configure(text=f"NF-e {nfe}  ({atual}/{total})  {m:02d}:{s:02d}")
        self._inserir_linha_upload(nfe, status)

    def _finalizar_upload(self, cancelado: bool, pasta: str = "", data_str: str = "") -> None:
        self._rodando = False
        self.btn_upload.configure(
            text="Iniciar Upload",
            fg_color=self._btn_upload_fg, hover_color=self._btn_upload_hover,
            command=self._iniciar_upload,
        )
        if cancelado:
            self.lbl_progresso.configure(text="Upload cancelado.")
        else:
            self.progressbar.set(1)
            self.lbl_progresso.configure(text="Upload concluído.")
            self._add_historico(
                tipo="upload",
                label=f"✅ {self._cnt_ok}  ·  ⚠ {self._cnt_dup}  ·  ❌ {self._cnt_nao}  —  {pasta}  ·  {data_str}",
                pasta=pasta,
                data_str=data_str,
                rows=list(self._rows),
            )

    # ------------------------------------------------------------------
    # HISTÓRICO
    # ------------------------------------------------------------------

    def _add_historico(self, tipo: str, label: str, pasta: str, data_str: str, rows: list) -> None:
        hora = datetime.now().strftime("%H:%M")
        self._hist.adicionar({
            "tipo": tipo, "label": f"{hora}  ·  {label}",
            "pasta": pasta, "data_str": data_str, "rows": rows,
        })

    def _restaurar(self, entry: dict) -> None:
        if self._rodando:
            return
        self._limpar_tabela()
        if entry["tipo"] == "renomear":
            self._reset_chips_renomear()
            self.hdr_upload.pack_forget()
            self.hdr_renomear.pack(fill="x")
            self._frame_upload_bar.pack_forget()
            for arquivo, nfe, status in entry["rows"]:
                self._inserir_linha_renomear(arquivo, nfe, status)
            self.entry_pasta_input.delete(0, "end")
            self.entry_pasta_input.insert(0, entry["pasta"])
        else:
            self._reset_chips_upload()
            self.hdr_renomear.pack_forget()
            self.hdr_upload.pack(fill="x")
            for nfe, status in entry["rows"]:
                self._inserir_linha_upload(nfe, status)
            self._pasta_output = entry["pasta"]
            self.entry_data.delete(0, "end")
            self.entry_data.insert(0, entry["data_str"])
            if not self._frame_upload_bar.winfo_ismapped():
                self._frame_upload_bar.pack(side="right")
        self.scroll._parent_canvas.yview_moveto(0)
        self.lbl_progresso.configure(text=f"Histórico: {entry['label']}")
        self.progressbar.set(1)

    # ------------------------------------------------------------------
    # CANCELAR / SAIR
    # ------------------------------------------------------------------

    def _cancelar(self) -> None:
        self._stop_event.set()

    def _sair(self) -> None:
        self._stop_event.set()
        self._on_logout()
