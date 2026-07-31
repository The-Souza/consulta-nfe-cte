import threading
from datetime import datetime
from typing import Callable

import customtkinter as ctk

from ui.widgets.chip import make_chip
from ui.widgets.dropdown import FilterDropdown
from ui.widgets.history import HistoryPanel
from ui.widgets.table import make_header, insert_row, clear_scroll
from ui.widgets.topbar import make_topbar
from ui.workers.search import SearchWorker
from utils.excel import export_excel, format_image

_COLS = [("Nº", 50), ("NF-e", 80), ("CT-e", 100), ("Imagem", 80), ("Status", 160)]

_FILTERS: dict[str, Callable[[dict], bool]] = {
    "Todos":          lambda r: True,
    "Sem imagem":     lambda r: r.get("Imagem") == "Não",
    "Com imagem":     lambda r: r.get("Imagem") == "Sim",
    "Sem CT-e":       lambda r: "Sem CT-e" in r["Status"],
    "Não cadastrada": lambda r: "Não cadastrada" in r["Status"],
    "Com CT-e (OK)":  lambda r: "OK" in r["Status"],
}


class SearchFrame(ctk.CTkFrame):
    def __init__(self, parent, session, user_name, on_logout, on_back=None):
        super().__init__(parent, fg_color="transparent")
        self._session      = session
        self._on_logout    = on_logout
        self._on_back    = on_back
        self._results    = []
        self._searching  = False
        self._stop_event = threading.Event()
        self._row_count    = 0
        self._build(user_name)

    # ------------------------------------------------------------------
    # LAYOUT
    # ------------------------------------------------------------------

    def _build(self, user_name: str) -> None:
        make_topbar(self, "Consulta NF-e / CT-e", user_name, self._logout,
                    on_back=self._back if self._on_back else None)
        main = ctk.CTkFrame(self, fg_color="transparent")
        main.pack(fill="both", expand=True, padx=16, pady=12)
        self._build_inputs(main)
        self._build_progress_row(main)
        self._build_table(main)
        self._build_footer(main)
        self._build_history(main)

    def _build_inputs(self, main: ctk.CTkFrame) -> None:
        row = ctk.CTkFrame(main, fg_color="transparent")
        row.pack(fill="x", pady=(0, 4))

        digits_only = (self.register(lambda v: v.isdigit() or v == ""), "%P")

        ctk.CTkLabel(row, text="NF-e inicial:").pack(side="left", padx=(0, 4))
        self.entry_start = ctk.CTkEntry(row, width=110, validate="key", validatecommand=digits_only)
        self.entry_start.pack(side="left", padx=(0, 16))

        ctk.CTkLabel(row, text="NF-e final:").pack(side="left", padx=(0, 4))
        self.entry_end = ctk.CTkEntry(row, width=110, validate="key", validatecommand=digits_only)
        self.entry_end.pack(side="left", padx=(0, 12))

        self.btn_search = ctk.CTkButton(row, text="Buscar", width=100, command=self._start_search)
        self.btn_search.pack(side="left", padx=(0, 6))
        self._btn_search_fg    = self.btn_search.cget("fg_color")
        self._btn_search_hover = self.btn_search.cget("hover_color")

        self.btn_clear = ctk.CTkButton(
            row, text="Limpar", width=100,
            fg_color="transparent", hover_color="#444",
            border_width=1, border_color="gray",
            command=self._clear,
        )
        self.btn_clear.pack(side="left")

        self.entry_start.bind("<Return>", lambda e: self.entry_end.focus())
        self.entry_end.bind("<Return>",   lambda e: self._start_search())

    def _build_progress_row(self, main: ctk.CTkFrame) -> None:
        row = ctk.CTkFrame(main, fg_color="transparent")
        row.pack(fill="x", pady=(4, 8))

        self.lbl_progress = ctk.CTkLabel(row, text="", anchor="w")
        self.lbl_progress.pack(side="left", fill="x", expand=True)

        ctk.CTkLabel(row, text="Filtrar:").pack(side="left", padx=(8, 4))
        self.option_filter = FilterDropdown(
            row, options=list(_FILTERS.keys()), command=self._on_filter_change, width=160,
        )
        self.option_filter.pack(side="left")

        self.progressbar = ctk.CTkProgressBar(main)
        self.progressbar.pack(fill="x", pady=(0, 10))
        self.progressbar.set(0)

    def _build_table(self, main: ctk.CTkFrame) -> None:
        make_header(main, _COLS).pack(fill="x")
        self.scroll = ctk.CTkScrollableFrame(main)
        self.scroll.pack(fill="both", expand=True, pady=(2, 6))

    def _build_footer(self, main: ctk.CTkFrame) -> None:
        bar = ctk.CTkFrame(main, fg_color="transparent")
        bar.pack(fill="x", pady=(4, 0))

        stat = ctk.CTkFrame(bar, fg_color="transparent")
        stat.pack(side="left")

        self.chip_ok      = make_chip(stat, "#4CAF50", "#1a3a1a")
        self.chip_no_cte  = make_chip(stat, "#FFC107", "#3a3000")
        self.chip_not_found = make_chip(stat, "#F44336", "#3a0f0f")
        self.chip_img_yes = make_chip(stat, "#4FC3F7", "#0d2b3a")
        self.chip_img_no  = make_chip(stat, "#BDBDBD", "#333333")
        self._reset_chips()

        self.btn_export = ctk.CTkButton(
            bar, text="Exportar Excel", width=140,
            command=self._export, state="disabled",
        )
        self.btn_export.pack(side="right")

    def _build_history(self, main: ctk.CTkFrame) -> None:
        self._hist = HistoryPanel(main, on_restore=self._restore)

    # ------------------------------------------------------------------
    # HELPERS VISUAIS
    # ------------------------------------------------------------------

    def _reset_chips(self) -> None:
        self.chip_ok.configure(text="✅  0  Com CT-e")
        self.chip_no_cte.configure(text="⚠  0  Sem CT-e")
        self.chip_not_found.configure(text="❌  0  Não cadastrada")
        self.chip_img_yes.configure(text="☑  0  Com imagem")
        self.chip_img_no.configure(text="❌  0  Sem imagem")

    def _update_chips(self) -> None:
        ok      = sum(1 for r in self._results if "OK"             in r["Status"])
        no_cte     = sum(1 for r in self._results if "Sem CT-e"       in r["Status"])
        not_found     = sum(1 for r in self._results if "Não cadastrada" in r["Status"])
        img_yes = sum(1 for r in self._results if r.get("Imagem") == "Sim")
        img_no  = sum(1 for r in self._results if r.get("Imagem") == "Não")
        self.chip_ok.configure(text=f"✅  {ok}  Com CT-e")
        self.chip_no_cte.configure(text=f"⚠  {no_cte}  Sem CT-e")
        self.chip_not_found.configure(text=f"❌  {not_found}  Não cadastrada")
        self.chip_img_yes.configure(text=f"☑  {img_yes}  Com imagem")
        self.chip_img_no.configure(text=f"❌  {img_no}  Sem imagem")

    def _insert_row(self, parent, r: dict) -> None:
        self._row_count += 1
        _COR = {
            "✅": ("#4CAF50", "#1a3a1a"),
            "⚠":  ("#FFC107", "#3a3000"),
            "❌": ("#F44336", "#3a0f0f"),
        }
        text_color, bg_color = next(
            ((f, b) for k, (f, b) in _COR.items() if k in r["Status"]),
            (None, None),
        )
        texts = [str(self._row_count), str(r["NF-e"]), r["CT-e"], format_image(r.get("Imagem"))]
        insert_row(parent, self._row_count, _COLS, texts, r["Status"], text_color, bg_color)

    def _clear_table(self) -> None:
        clear_scroll(self.scroll)
        self._results   = []
        self._row_count = 0

    # ------------------------------------------------------------------
    # AÇÕES
    # ------------------------------------------------------------------

    def _back(self) -> None:
        self._stop_event.set()
        self._on_back()

    def _logout(self) -> None:
        self._stop_event.set()
        self._on_logout()

    def _start_search(self) -> None:
        if self._searching:
            return
        try:
            start = int(self.entry_start.get().strip())
            end   = int(self.entry_end.get().strip())
        except ValueError:
            self.lbl_progress.configure(text="⚠ Digite números válidos.")
            return
        if start > end:
            self.lbl_progress.configure(text="⚠ NF-e inicial deve ser menor ou igual à final.")
            return

        self._clear_table()
        self._searching = True
        self._stop_event.clear()
        self.option_filter.set("Todos")
        self._reset_chips()
        self.progressbar.set(0)
        self.btn_clear.configure(state="disabled")
        self.btn_export.configure(state="disabled")
        self.btn_search.configure(
            text="⏹ Cancelar",
            fg_color=("#c0392b", "#7b241c"),
            hover_color=("#a93226", "#641e16"),
            command=self._cancel,
        )

        worker = SearchWorker(
            session=self._session,
            start=start,
            end=end,
            stop_event=self._stop_event,
            after_fn=self.after,
            on_update=self._add_row,
            on_done=lambda: self._finish(start, end, cancelled=False),
            on_cancel=lambda: self._finish(start, end, cancelled=True),
        )
        threading.Thread(target=worker.run, daemon=True).start()

    def _cancel(self) -> None:
        self._stop_event.set()

    # ------------------------------------------------------------------
    # FILTRO
    # ------------------------------------------------------------------

    def _on_filter_change(self, _value: str = "") -> None:
        self._redraw_table()

    def _redraw_table(self) -> None:
        clear_scroll(self.scroll)
        self._row_count = 0
        predicate = _FILTERS[self.option_filter.get()]
        for r in self._results:
            if predicate(r):
                self._insert_row(self.scroll, r)

    # ------------------------------------------------------------------
    # ATUALIZAÇÃO DA TABELA
    # ------------------------------------------------------------------

    def _add_row(self, r: dict, prog: float, current: int, total: int, elapsed: float) -> None:
        self._results.append(r)
        self.progressbar.set(prog)
        m, s = divmod(int(elapsed), 60)
        self.lbl_progress.configure(text=f"NF-e {r['NF-e']}  ({current}/{total})  {m:02d}:{s:02d}")
        if _FILTERS[self.option_filter.get()](r):
            self._insert_row(self.scroll, r)
        self._update_chips()

    # ------------------------------------------------------------------
    # FINALIZAÇÃO
    # ------------------------------------------------------------------

    def _finish(self, start: int, end: int, cancelled: bool) -> None:
        self._searching = False
        self.btn_search.configure(
            text="Buscar",
            fg_color=self._btn_search_fg,
            hover_color=self._btn_search_hover,
            command=self._start_search,
            state="normal",
        )
        self.btn_clear.configure(state="normal")

        if cancelled:
            self.lbl_progress.configure(text="Busca cancelada.")
        else:
            self.progressbar.set(1)
            self.lbl_progress.configure(text="Consulta concluída.")
            self._update_chips()

        if self._results:
            self.btn_export.configure(state="normal")
            self._add_history(start, end, list(self._results))

    # ------------------------------------------------------------------
    # LIMPAR
    # ------------------------------------------------------------------

    def _clear(self) -> None:
        self.entry_start.delete(0, "end")
        self.entry_end.delete(0, "end")
        self._clear_table()
        self.lbl_progress.configure(text="")
        self.progressbar.set(0)
        self.option_filter.set("Todos")
        self._reset_chips()
        self.btn_export.configure(state="disabled")
        self.entry_start.focus()

    # ------------------------------------------------------------------
    # EXPORTAR EXCEL
    # ------------------------------------------------------------------

    def _export(self) -> None:
        if not self._results:
            return
        filename = export_excel(self._results)
        self.lbl_progress.configure(text=f"✅ Salvo: {filename}")

    # ------------------------------------------------------------------
    # HISTÓRICO
    # ------------------------------------------------------------------

    def _add_history(self, start: int, end: int, results: list) -> None:
        hour  = datetime.now().strftime("%H:%M")
        label = f"{hour}  ·  NF-e {start} → {end}  ({len(results)} itens)"
        self._hist.add({"label": label, "start": start, "end": end, "results": results})

    def _restore(self, entry: dict) -> None:
        if self._searching:
            return
        self.entry_start.delete(0, "end")
        self.entry_start.insert(0, str(entry["start"]))
        self.entry_end.delete(0, "end")
        self.entry_end.insert(0, str(entry["end"]))

        self._clear_table()
        self._results = list(entry["results"])
        self.option_filter.set("Todos")
        self._redraw_table()
        self.scroll._parent_canvas.yview_moveto(0)

        self._update_chips()
        self.lbl_progress.configure(text=f"Histórico: {entry['label']}")
        self.progressbar.set(1)
        self.btn_export.configure(state="normal")
