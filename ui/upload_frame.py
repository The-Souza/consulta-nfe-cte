import os
import shutil
import threading
import time
from datetime import datetime
from pathlib import Path
from tkinter import filedialog

import customtkinter as ctk

import api
import ocr

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
        self._historico: list[dict] = []
        self._hist_visible = False
        self._cnt_ok = self._cnt_dup = self._cnt_nao = 0
        self._rows: list = []
        self._build(usuario_nome)

    # ------------------------------------------------------------------
    # LAYOUT
    # ------------------------------------------------------------------

    def _build(self, usuario_nome: str) -> None:
        self._build_topbar(usuario_nome)
        main = ctk.CTkFrame(self, fg_color="transparent")
        main.pack(fill="both", expand=True, padx=16, pady=12)
        self._build_etapa_renomear(main)
        self._build_progresso(main)
        self._build_tabela(main)
        self._build_rodape(main)
        self._build_historico(main)

    def _build_topbar(self, usuario_nome: str) -> None:
        topbar = ctk.CTkFrame(self, height=40, corner_radius=0)
        topbar.pack(fill="x")
        topbar.pack_propagate(False)

        ctk.CTkLabel(
            topbar, text="Upload Canhotos",
            font=ctk.CTkFont(size=14, weight="bold"),
        ).pack(side="left", padx=16)

        ctk.CTkButton(
            topbar, text="Sair", width=72, height=32,
            fg_color="transparent", hover_color="#444",
            border_width=1, border_color="gray",
            command=self._sair,
        ).pack(side="right", padx=14, pady=9)

        if usuario_nome:
            ctk.CTkLabel(
                topbar, text=f"Olá, {usuario_nome} ·",
                font=ctk.CTkFont(size=12), text_color="gray",
            ).pack(side="right", padx=(4, 0))

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

    def _build_progresso(self, main: ctk.CTkFrame) -> None:
        self.lbl_progresso = ctk.CTkLabel(main, text="", anchor="w")
        self.lbl_progresso.pack(fill="x", pady=(4, 2))
        self.progressbar = ctk.CTkProgressBar(main)
        self.progressbar.pack(fill="x", pady=(0, 8))
        self.progressbar.set(0)

    def _build_tabela(self, main: ctk.CTkFrame) -> None:
        # Container fixo — mantém a posição do header no layout.
        # Os dois headers trocam dentro dele sem precisar de before=.
        hdr_slot = ctk.CTkFrame(main, fg_color="transparent")
        hdr_slot.pack(fill="x")

        def _hdr(cols):
            f = ctk.CTkFrame(hdr_slot, height=36)
            f.pack_propagate(False)
            ctk.CTkFrame(f, width=8, fg_color="transparent").pack(side="left")
            for txt, w in cols:
                cell = ctk.CTkFrame(f, width=w, fg_color="transparent")
                cell.pack(side="left")
                cell.pack_propagate(False)
                ctk.CTkLabel(cell, text=txt, font=ctk.CTkFont(weight="bold"), anchor="center").pack(fill="both", expand=True)
            return f

        self.hdr_renomear = _hdr(_COLS_R)
        self.hdr_renomear.pack(fill="x")
        self.hdr_upload = _hdr(_COLS_U)

        self.scroll = ctk.CTkScrollableFrame(main)
        self.scroll.pack(fill="both", expand=True, pady=(2, 6))
        self._row_count = 0

    def _build_rodape(self, main: ctk.CTkFrame) -> None:
        bar = ctk.CTkFrame(main, fg_color="transparent")
        bar.pack(fill="x", pady=(4, 0))

        # Chips — lado esquerdo
        stat = ctk.CTkFrame(bar, fg_color="transparent")
        stat.pack(side="left")
        self.chip_ok  = self._fazer_chip(stat, "#4CAF50", "#1a3a1a")
        self.chip_dup = self._fazer_chip(stat, "#FFC107", "#3a3000")
        self.chip_nao = self._fazer_chip(stat, "#F44336", "#3a0f0f")
        self._reset_chips_renomear()

        # Controles de upload — lado direito (aparece após renomear)
        self._frame_upload_bar = ctk.CTkFrame(bar, fg_color="transparent")

        self.entry_pasta_output = ctk.CTkEntry(
            self._frame_upload_bar, width=190, placeholder_text="Pasta renomeada",
        )
        self.entry_pasta_output.pack(side="left", padx=(0, 4))
        ctk.CTkButton(
            self._frame_upload_bar, text="...", width=34,
            fg_color="transparent", border_width=1, border_color="gray",
            command=self._selecionar_pasta_output,
        ).pack(side="left", padx=(0, 10))

        self.entry_data = ctk.CTkEntry(
            self._frame_upload_bar, width=115, placeholder_text="DD/MM/AAAA",
        )
        self.entry_data.pack(side="left", padx=(0, 8))

        ctk.CTkButton(
            self._frame_upload_bar, text="Limpar", width=80,
            fg_color="transparent", hover_color="#444",
            border_width=1, border_color="gray",
            command=self._limpar_upload_bar,
        ).pack(side="left", padx=(0, 8))

        self.btn_upload = ctk.CTkButton(
            self._frame_upload_bar, text="Iniciar Upload", width=125,
            command=self._iniciar_upload,
        )
        self.btn_upload.pack(side="left")
        self._btn_upload_fg    = self.btn_upload.cget("fg_color")
        self._btn_upload_hover = self.btn_upload.cget("hover_color")

    def _build_historico(self, main: ctk.CTkFrame) -> None:
        self.btn_hist_toggle = ctk.CTkButton(
            main, text="▶  Histórico (0)",
            fg_color="transparent", hover_color="#444",
            anchor="w", height=28,
            command=self._toggle_historico,
        )
        self.btn_hist_toggle.pack(fill="x", pady=(10, 0))
        self.hist_scroll = ctk.CTkScrollableFrame(main, height=88)

    # ------------------------------------------------------------------
    # HELPERS VISUAIS
    # ------------------------------------------------------------------

    def _fazer_chip(self, parent, cor_texto: str, cor_fundo: str) -> ctk.CTkLabel:
        frame = ctk.CTkFrame(parent, fg_color=cor_fundo, corner_radius=20)
        frame.pack(side="left", padx=(0, 8))
        lbl = ctk.CTkLabel(frame, text="", text_color=cor_texto, font=ctk.CTkFont(size=11))
        lbl.pack(padx=12, pady=3)
        return lbl

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

    def _limpar_upload_bar(self) -> None:
        self.entry_pasta_output.delete(0, "end")
        self.entry_data.delete(0, "end")
        self._limpar_tabela()
        self.lbl_progresso.configure(text="")
        self.progressbar.set(0)
        self._reset_chips_upload()

    def _limpar_tabela(self) -> None:
        for w in self.scroll.winfo_children():
            w.destroy()
        self.scroll._parent_canvas.yview_moveto(0)
        self._row_count = 0

    def _inserir_linha_renomear(self, arquivo: str, nfe: str | None, status: str) -> None:
        self._row_count += 1
        row_bg = "#252525" if self._row_count % 2 == 0 else "transparent"
        mono   = ctk.CTkFont(family="Consolas", size=12)
        linha  = ctk.CTkFrame(self.scroll, height=30, fg_color=row_bg)
        linha.pack(fill="x")
        linha.pack_propagate(False)

        for (_, w), txt in zip(_COLS_R[:3], [str(self._row_count), arquivo, nfe or "-"]):
            cell = ctk.CTkFrame(linha, width=w, height=30, fg_color="transparent")
            cell.pack(side="left")
            cell.pack_propagate(False)
            ctk.CTkLabel(cell, text=txt, anchor="center", font=mono).pack(fill="both", expand=True)

        _COR = {
            "ok":             ("✅ Renomeada",  "#4CAF50", "#1a3a1a"),
            "duplicata":      ("⚠ Duplicata",   "#FFC107", "#3a3000"),
            "nao_encontrada": ("❌ Não lida",   "#F44336", "#3a0f0f"),
            "erro":           ("❌ Erro",        "#F44336", "#3a0f0f"),
        }
        label, cor_fg, cor_bg = _COR.get(status, ("❌ Erro", "#F44336", "#3a0f0f"))
        _, status_w = _COLS_R[3]
        cell = ctk.CTkFrame(linha, width=status_w, height=30, fg_color="transparent")
        cell.pack(side="left")
        cell.pack_propagate(False)
        badge = ctk.CTkFrame(cell, fg_color=cor_bg, corner_radius=9, height=18)
        badge.place(relx=0.5, rely=0.5, anchor="center")
        ctk.CTkLabel(badge, text=label, text_color=cor_fg,
                     font=ctk.CTkFont(size=10), height=16).pack(side="left", padx=8, pady=0)

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
        row_bg = "#252525" if self._row_count % 2 == 0 else "transparent"
        mono   = ctk.CTkFont(family="Consolas", size=12)
        linha  = ctk.CTkFrame(self.scroll, height=30, fg_color=row_bg)
        linha.pack(fill="x")
        linha.pack_propagate(False)

        for (_, w), txt in zip(_COLS_U[:2], [str(self._row_count), nfe]):
            cell = ctk.CTkFrame(linha, width=w, height=30, fg_color="transparent")
            cell.pack(side="left")
            cell.pack_propagate(False)
            ctk.CTkLabel(cell, text=txt, anchor="center", font=mono).pack(fill="both", expand=True)

        _COR = {"✅": ("#4CAF50", "#1a3a1a"), "⚠": ("#FFC107", "#3a3000"), "❌": ("#F44336", "#3a0f0f")}
        cor_fg, cor_bg = next(((f, b) for k, (f, b) in _COR.items() if k in status), ("#aaa", "transparent"))
        _, status_w = _COLS_U[2]
        cell = ctk.CTkFrame(linha, width=status_w, height=30, fg_color="transparent")
        cell.pack(side="left")
        cell.pack_propagate(False)
        badge = ctk.CTkFrame(cell, fg_color=cor_bg, corner_radius=9, height=18)
        badge.place(relx=0.5, rely=0.5, anchor="center")
        ctk.CTkLabel(badge, text=status, text_color=cor_fg,
                     font=ctk.CTkFont(size=10), height=16).pack(side="left", padx=8, pady=0)

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

    def _selecionar_pasta_output(self) -> None:
        pasta = filedialog.askdirectory(title="Selecionar pasta renomeada")
        if pasta:
            self.entry_pasta_output.delete(0, "end")
            self.entry_pasta_output.insert(0, pasta)

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
        threading.Thread(target=self._renomear_thread, args=(pasta,), daemon=True).start()

    def _renomear_thread(self, pasta: str) -> None:
        output = Path(pasta).parent / "renamed"
        output.mkdir(exist_ok=True)

        files = [f for f in os.listdir(pasta) if f.lower().endswith((".jpg", ".jpeg", ".png"))]
        total = len(files)
        t0 = time.time()

        for i, arquivo in enumerate(files):
            if self._stop_event.is_set():
                self.after(0, lambda: self._finalizar_renomear(cancelado=True))
                return

            path = os.path.join(pasta, arquivo)
            nfe    = None
            status = "erro"
            try:
                nfe = ocr.process_image(path)
                if nfe is None:
                    status = "nao_encontrada"
                else:
                    novo = output / f"{nfe}.jpg"
                    if novo.exists():
                        status = "duplicata"
                    else:
                        shutil.move(str(path), str(novo))
                        status = "ok"
            except Exception:
                status = "erro"

            prog    = (i + 1) / total
            elapsed = time.time() - t0
            self.after(0, self._atualizar_renomear, arquivo, nfe, status, prog, i + 1, total, elapsed)

        self.after(0, lambda: self._finalizar_renomear(cancelado=False, output=str(output)))

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
        self.entry_pasta_output.delete(0, "end")
        self.entry_pasta_output.insert(0, output)
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
        pasta = self.entry_pasta_output.get().strip() or "renamed"
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
        threading.Thread(target=self._upload_thread, args=(pasta, data_lote, data_str), daemon=True).start()

    def _upload_thread(self, pasta: str, data_lote: str, data_str: str) -> None:
        pendente_dir = Path(pasta).parent / "pendentes"
        nao_pend_dir = Path(pasta).parent / "nao_pendentes"
        pendente_dir.mkdir(exist_ok=True)
        nao_pend_dir.mkdir(exist_ok=True)

        files = [f for f in os.listdir(pasta) if f.lower().endswith(".jpg")]
        total = len(files)
        t0 = time.time()

        for i, arquivo in enumerate(files):
            if self._stop_event.is_set():
                self.after(0, lambda: self._finalizar_upload(cancelado=True, pasta=pasta, data_str=data_str))
                return

            nfe  = Path(arquivo).stem
            path = Path(pasta) / arquivo

            try:
                oid, status_api = api.consultar_canhoto_upload(self._session, nfe)

                if oid is None:
                    status = "❌ Não encontrada"
                elif status_api != "PENDENTE":
                    shutil.move(str(path), str(nao_pend_dir / arquivo))
                    status = f"⚠ {status_api}"
                else:
                    full_data = api.get_canhoto_completo(self._session, oid)
                    ok, err = api.upload_canhoto(self._session, nfe, path, full_data, data_lote)
                    if ok:
                        shutil.move(str(path), str(pendente_dir / arquivo))
                        status = "✅ Enviado"
                    else:
                        status = f"❌ {err}"
            except Exception as e:
                status = f"❌ {api.erro_amigavel(e)}"

            prog    = (i + 1) / total
            elapsed = time.time() - t0
            self.after(0, self._atualizar_upload, nfe, status, prog, i + 1, total, elapsed)

        self.after(0, lambda: self._finalizar_upload(cancelado=False, pasta=pasta, data_str=data_str))

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
        self._historico.insert(0, {
            "tipo": tipo, "label": f"{hora}  ·  {label}",
            "pasta": pasta, "data_str": data_str, "rows": rows,
        })
        prefix = "▼" if self._hist_visible else "▶"
        self.btn_hist_toggle.configure(text=f"{prefix}  Histórico ({len(self._historico)})")
        self._rebuild_historico()

    def _toggle_historico(self) -> None:
        self._hist_visible = not self._hist_visible
        prefix = "▼" if self._hist_visible else "▶"
        self.btn_hist_toggle.configure(text=f"{prefix}  Histórico ({len(self._historico)})")
        if self._hist_visible:
            self.hist_scroll.pack(fill="x", pady=(2, 0))
        else:
            self.hist_scroll.pack_forget()

    def _rebuild_historico(self) -> None:
        for w in self.hist_scroll.winfo_children():
            w.destroy()
        for entry in self._historico:
            ctk.CTkButton(
                self.hist_scroll,
                text=entry["label"],
                fg_color="transparent", hover_color="#3a3a3a",
                anchor="w", height=28,
                command=lambda e=entry: self._restaurar(e),
            ).pack(fill="x", pady=1)

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
            self.entry_pasta_output.delete(0, "end")
            self.entry_pasta_output.insert(0, entry["pasta"])
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
