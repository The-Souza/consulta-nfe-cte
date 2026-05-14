import threading
import time
from datetime import datetime

import customtkinter as ctk
import pandas as pd

import api

# (header_text, width_px) — definição única usada em header e linhas
_COLS = [("Nº", 50), ("NF-e", 80), ("CT-e", 100), ("Status", 160)]


class BuscaFrame(ctk.CTkFrame):
    def __init__(self, parent, session, usuario_nome, on_logout):
        super().__init__(parent, fg_color="transparent")
        self._session      = session
        self._on_logout    = on_logout
        self._resultados   = []
        self._historico    = []
        self._buscando     = False
        self._hist_visible = False
        self._stop_event   = threading.Event()
        self._row_count    = 0
        self._build(usuario_nome)

    # ------------------------------------------------------------------
    # LAYOUT
    # ------------------------------------------------------------------

    def _build(self, usuario_nome: str) -> None:
        self._build_topbar(usuario_nome)
        main = ctk.CTkFrame(self, fg_color="transparent")
        main.pack(fill="both", expand=True, padx=16, pady=12)
        self._build_inputs(main)
        self._build_progresso(main)
        self._build_tabela(main)
        self._build_rodape(main)
        self._build_historico(main)

    def _build_topbar(self, usuario_nome: str) -> None:
        topbar = ctk.CTkFrame(self, height=40, corner_radius=0)
        topbar.pack(fill="x")
        topbar.pack_propagate(False)

        ctk.CTkLabel(
            topbar, text="Consulta NF-e / CT-e",
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

    def _build_inputs(self, main: ctk.CTkFrame) -> None:
        row = ctk.CTkFrame(main, fg_color="transparent")
        row.pack(fill="x", pady=(0, 4))

        so_numeros = (self.register(lambda v: v.isdigit() or v == ""), "%P")

        ctk.CTkLabel(row, text="NF-e inicial:").pack(side="left", padx=(0, 4))
        self.entry_inicio = ctk.CTkEntry(row, width=110, validate="key", validatecommand=so_numeros)
        self.entry_inicio.pack(side="left", padx=(0, 16))

        ctk.CTkLabel(row, text="NF-e final:").pack(side="left", padx=(0, 4))
        self.entry_fim = ctk.CTkEntry(row, width=110, validate="key", validatecommand=so_numeros)
        self.entry_fim.pack(side="left", padx=(0, 12))

        self.btn_buscar = ctk.CTkButton(row, text="Buscar", width=100, command=self._iniciar_busca)
        self.btn_buscar.pack(side="left", padx=(0, 6))
        self._btn_buscar_fg    = self.btn_buscar.cget("fg_color")
        self._btn_buscar_hover = self.btn_buscar.cget("hover_color")

        self.btn_limpar = ctk.CTkButton(
            row, text="Limpar", width=100,
            fg_color="transparent", hover_color="#444",
            border_width=1, border_color="gray",
            command=self._limpar,
        )
        self.btn_limpar.pack(side="left")

        self.entry_inicio.bind("<Return>", lambda e: self.entry_fim.focus())
        self.entry_fim.bind("<Return>",    lambda e: self._iniciar_busca())

    def _build_progresso(self, main: ctk.CTkFrame) -> None:
        self.lbl_progresso = ctk.CTkLabel(main, text="", anchor="w")
        self.lbl_progresso.pack(fill="x", pady=(4, 2))

        self.progressbar = ctk.CTkProgressBar(main)
        self.progressbar.pack(fill="x", pady=(0, 8))
        self.progressbar.set(0)

    def _build_tabela(self, main: ctk.CTkFrame) -> None:
        hdr = ctk.CTkFrame(main, height=36)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        ctk.CTkFrame(hdr, width=8, fg_color="transparent").pack(side="left")
        for txt, w in _COLS:
            cell = ctk.CTkFrame(hdr, width=w, fg_color="transparent")
            cell.pack(side="left")
            cell.pack_propagate(False)
            ctk.CTkLabel(cell, text=txt, font=ctk.CTkFont(weight="bold"), anchor="center").pack(fill="both", expand=True)

        self.scroll = ctk.CTkScrollableFrame(main)
        self.scroll.pack(fill="both", expand=True, pady=(2, 6))

    def _build_rodape(self, main: ctk.CTkFrame) -> None:
        bar = ctk.CTkFrame(main, fg_color="transparent")
        bar.pack(fill="x", pady=(4, 0))

        stat = ctk.CTkFrame(bar, fg_color="transparent")
        stat.pack(side="left")

        self.chip_ok  = self._fazer_chip(stat, "#4CAF50", "#1a3a1a")
        self.chip_sem = self._fazer_chip(stat, "#FFC107", "#3a3000")
        self.chip_nao = self._fazer_chip(stat, "#F44336", "#3a0f0f")
        self._reset_chips()

        self.btn_exportar = ctk.CTkButton(
            bar, text="Exportar Excel", width=140,
            command=self._exportar, state="disabled",
        )
        self.btn_exportar.pack(side="right")

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

    def _reset_chips(self) -> None:
        self.chip_ok.configure(text="✅  0  Com CT-e")
        self.chip_sem.configure(text="⚠  0  Sem CT-e")
        self.chip_nao.configure(text="❌  0  Não cadastrada")

    def _atualizar_chips(self) -> None:
        ok  = sum(1 for r in self._resultados if "OK"             in r["Status"])
        sem = sum(1 for r in self._resultados if "Sem CT-e"       in r["Status"])
        nao = sum(1 for r in self._resultados if "Não cadastrada" in r["Status"])
        self.chip_ok.configure(text=f"✅  {ok}  Com CT-e")
        self.chip_sem.configure(text=f"⚠  {sem}  Sem CT-e")
        self.chip_nao.configure(text=f"❌  {nao}  Não cadastrada")

    def _inserir_linha(self, parent, r: dict) -> None:
        self._row_count += 1
        row_bg = "#252525" if self._row_count % 2 == 0 else "transparent"

        _COR = {
            "✅": ("#4CAF50", "#1a3a1a"),
            "⚠":  ("#FFC107", "#3a3000"),
            "❌": ("#F44336", "#3a0f0f"),
        }
        cor_fg, cor_bg_badge = next(
            ((f, b) for k, (f, b) in _COR.items() if k in r["Status"]),
            (None, None),
        )

        mono  = ctk.CTkFont(family="Consolas", size=12)
        linha = ctk.CTkFrame(parent, height=30, fg_color=row_bg)
        linha.pack(fill="x", pady=0)
        linha.pack_propagate(False)

        for (_, w), txt in zip(_COLS[:3], [str(self._row_count), str(r["NF-e"]), r["CT-e"]]):
            cell = ctk.CTkFrame(linha, width=w, height=30, fg_color="transparent")
            cell.pack(side="left")
            cell.pack_propagate(False)
            ctk.CTkLabel(cell, text=txt, anchor="center", font=mono).pack(fill="both", expand=True)

        _, status_w = _COLS[3]
        cell = ctk.CTkFrame(linha, width=status_w, height=30, fg_color="transparent")
        cell.pack(side="left")
        cell.pack_propagate(False)
        if cor_fg:
            badge = ctk.CTkFrame(cell, fg_color=cor_bg_badge, corner_radius=9, height=18)
            badge.place(relx=0.5, rely=0.5, anchor="center")
            ctk.CTkLabel(badge, text=r["Status"], text_color=cor_fg,
                        font=ctk.CTkFont(size=10), height=20).pack(side="left", padx=8, pady=0)
        else:
            ctk.CTkLabel(cell, text=r["Status"], anchor="center").pack(fill="both", expand=True)

    def _limpar_tabela(self) -> None:
        for w in self.scroll.winfo_children():
            w.destroy()
        self.scroll._parent_canvas.yview_moveto(0)
        self._resultados = []
        self._row_count  = 0

    # ------------------------------------------------------------------
    # AÇÕES
    # ------------------------------------------------------------------

    def _sair(self) -> None:
        self._stop_event.set()
        self._on_logout()

    def _iniciar_busca(self) -> None:
        if self._buscando:
            return
        try:
            inicio = int(self.entry_inicio.get().strip())
            fim    = int(self.entry_fim.get().strip())
        except ValueError:
            self.lbl_progresso.configure(text="⚠ Digite números válidos.")
            return
        if inicio > fim:
            self.lbl_progresso.configure(text="⚠ NF-e inicial deve ser menor ou igual à final.")
            return

        self._limpar_tabela()
        self._buscando = True
        self._stop_event.clear()
        self._reset_chips()
        self.progressbar.set(0)
        self.btn_limpar.configure(state="disabled")
        self.btn_exportar.configure(state="disabled")
        self.btn_buscar.configure(
            text="⏹ Cancelar",
            fg_color=("#c0392b", "#7b241c"),
            hover_color=("#a93226", "#641e16"),
            command=self._cancelar,
        )

        threading.Thread(target=self._buscar_thread, args=(inicio, fim), daemon=True).start()

    def _cancelar(self) -> None:
        self._stop_event.set()

    # ------------------------------------------------------------------
    # THREAD DE BUSCA
    # ------------------------------------------------------------------

    def _buscar_thread(self, inicio: int, fim: int) -> None:
        total = fim - inicio + 1
        t0    = time.time()

        for i, nfe in enumerate(range(inicio, fim + 1)):
            if self._stop_event.is_set():
                self.after(0, lambda: self._finalizar(inicio, fim, cancelado=True))
                return

            try:
                cte, status = api.consultar_canhoto(self._session, nfe)
            except Exception as e:
                cte, status = "-", f"❌ {api.erro_amigavel(e)}"

            r = {"NF-e": nfe, "CT-e": cte, "Status": status}
            self._resultados.append(r)

            prog    = (i + 1) / total
            elapsed = time.time() - t0
            self.after(0, self._adicionar_linha, r, prog, i + 1, total, elapsed)

            time.sleep(0.05)

        self.after(0, lambda: self._finalizar(inicio, fim, cancelado=False))

    # ------------------------------------------------------------------
    # ATUALIZAÇÃO DA TABELA
    # ------------------------------------------------------------------

    def _adicionar_linha(self, r: dict, prog: float, atual: int, total: int, elapsed: float) -> None:
        self.progressbar.set(prog)
        m, s = divmod(int(elapsed), 60)
        self.lbl_progresso.configure(text=f"NF-e {r['NF-e']}  ({atual}/{total})  {m:02d}:{s:02d}")
        self._inserir_linha(self.scroll, r)
        self._atualizar_chips()

    # ------------------------------------------------------------------
    # FINALIZAÇÃO
    # ------------------------------------------------------------------

    def _finalizar(self, inicio: int, fim: int, cancelado: bool) -> None:
        self._buscando = False
        self.btn_buscar.configure(
            text="Buscar",
            fg_color=self._btn_buscar_fg,
            hover_color=self._btn_buscar_hover,
            command=self._iniciar_busca,
            state="normal",
        )
        self.btn_limpar.configure(state="normal")

        if cancelado:
            self.lbl_progresso.configure(text="Busca cancelada.")
        else:
            self.progressbar.set(1)
            self.lbl_progresso.configure(text="Consulta concluída.")
            self._atualizar_chips()

        if self._resultados:
            self.btn_exportar.configure(state="normal")
            self._add_historico(inicio, fim, list(self._resultados))

    # ------------------------------------------------------------------
    # LIMPAR
    # ------------------------------------------------------------------

    def _limpar(self) -> None:
        self.entry_inicio.delete(0, "end")
        self.entry_fim.delete(0, "end")
        self._limpar_tabela()
        self.lbl_progresso.configure(text="")
        self.progressbar.set(0)
        self._reset_chips()
        self.btn_exportar.configure(state="disabled")

    # ------------------------------------------------------------------
    # EXPORTAR EXCEL
    # ------------------------------------------------------------------

    def _exportar(self) -> None:
        if not self._resultados:
            return
        inicio  = self._resultados[0]["NF-e"]
        fim     = self._resultados[-1]["NF-e"]
        arquivo = f"consulta_nfe_{inicio}_{fim}.xlsx"
        df = pd.DataFrame([
            {"NF-e": r["NF-e"], "CT-e": r["CT-e"], "Status": r["Status"].split(" ", 1)[-1]}
            for r in self._resultados
        ])
        df.to_excel(arquivo, index=False)
        self.lbl_progresso.configure(text=f"✅ Salvo: {arquivo}")

    # ------------------------------------------------------------------
    # HISTÓRICO
    # ------------------------------------------------------------------

    def _add_historico(self, inicio: int, fim: int, resultados: list) -> None:
        hora  = datetime.now().strftime("%H:%M")
        label = f"{hora}  ·  NF-e {inicio} → {fim}  ({len(resultados)} itens)"
        self._historico.insert(0, {"label": label, "inicio": inicio, "fim": fim, "resultados": resultados})
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
        if self._buscando:
            return
        self.entry_inicio.delete(0, "end")
        self.entry_inicio.insert(0, str(entry["inicio"]))
        self.entry_fim.delete(0, "end")
        self.entry_fim.insert(0, str(entry["fim"]))

        self._limpar_tabela()
        self._resultados = list(entry["resultados"])
        for r in self._resultados:
            self._inserir_linha(self.scroll, r)
        self.scroll._parent_canvas.yview_moveto(0)

        self._atualizar_chips()
        self.lbl_progresso.configure(text=f"Histórico: {entry['label']}")
        self.progressbar.set(1)
        self.btn_exportar.configure(state="normal")
