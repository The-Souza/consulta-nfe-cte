import threading
from datetime import datetime
from typing import Callable

import customtkinter as ctk

from ui import theme
from ui.widgets.banner import Banner
from ui.widgets.buttons import restore_button, show_cancel
from ui.widgets.chip import make_chip
from ui.widgets.dropdown import FilterDropdown
from ui.widgets.history import HistoryPanel
from ui.widgets.progress import set_message
from ui.widgets.table import make_header, insert_row, clear_scroll
from ui.widgets.topbar import make_topbar
from ui.workers.search import SearchCallbacks, SearchWorker
from utils.excel import export_excel, format_image
from utils.nfe_query import CONFIRM_ABOVE, parse_query
from utils.status import CONNECTION_FAILED, SEARCH_NO_CTE, SEARCH_NOT_FOUND, SEARCH_OK, Tone, search_tone

_COLS = [("Nº", 50), ("NF-e", 80), ("CT-e", 100), ("Imagem", 80), ("Status", 160)]
_HISTORY_QUERY_CHARS = 40

_FILTERS: dict[str, Callable[[dict], bool]] = {
    "Todos":            lambda r: True,
    "Sem imagem":       lambda r: r.get("Imagem") == "Não",
    "Com imagem":       lambda r: r.get("Imagem") == "Sim",
    "Sem CT-e":         lambda r: r["Status"] == SEARCH_NO_CTE,
    "Não cadastrada":   lambda r: r["Status"] == SEARCH_NOT_FOUND,
    "Com CT-e (OK)":    lambda r: r["Status"] == SEARCH_OK,
    "Falha de conexão": lambda r: r["Status"] == CONNECTION_FAILED,
}


class SearchFrame(ctk.CTkFrame):
    def __init__(self, parent, session, user_name, on_logout, on_back=None, relogin: Callable[[], None] | None = None):
        super().__init__(parent, fg_color="transparent")
        self._session      = session
        self._relogin      = relogin
        self._on_logout    = on_logout
        self._on_back    = on_back
        self._results: dict[int, dict] = {}  # NF-e -> row, in query order
        self._row_widgets: dict[int, tuple] = {}  # NF-e -> (row frame, row number) of the rows on screen
        self._current_entry: dict | None = None  # history entry of the results on screen
        self._searching  = False
        self._stop_event = threading.Event()
        self._row_count    = 0
        self._btn_search_style: dict = {}
        self._last_query: str | None = None  # field text the parse label was computed for
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

        field = ctk.CTkFrame(row, fg_color="transparent")
        field.pack(side="left", padx=(0, 12))
        labels = ctk.CTkFrame(field, fg_color="transparent")
        labels.pack(fill="x")
        ctk.CTkLabel(
            labels, text="NF-es", text_color=theme.TEXT_MUTED, font=theme.font(theme.FONT_SIZE_SM), height=18,
        ).pack(side="left")
        self.lbl_parse = ctk.CTkLabel(labels, text="", font=theme.font(theme.FONT_SIZE_SM), height=18)
        self.lbl_parse.pack(side="right")
        self.entry_query = ctk.CTkEntry(
            field, width=420, height=38, placeholder_text="4516661 · 4516661-4516680 · 4516661, 4516670",
            corner_radius=theme.RADIUS_INPUT, border_width=1,
            fg_color=theme.INPUT_BG, border_color=theme.BORDER_INPUT,
            text_color=theme.TEXT, placeholder_text_color=theme.TEXT_MUTED,
            font=theme.font(theme.FONT_SIZE_INPUT, mono=True),
        )
        self.entry_query.pack(pady=(theme.SPACE_XS, 0))

        self.btn_search = ctk.CTkButton(row, text="Buscar", width=100, height=38, command=self._start_search)
        self.btn_search.pack(side="left", padx=(0, 6), anchor="s")

        self.btn_clear = ctk.CTkButton(
            row, text="Limpar", width=100, height=38,
            fg_color="transparent", hover_color=theme.SURFACE_2,
            border_width=1, border_color=theme.BORDER_INPUT,
            command=self._clear,
        )
        self.btn_clear.pack(side="left", anchor="s")

        # Shown only when the results have connection failures.
        text_color, bg_color = theme.STATUS[Tone.CONNECTION.value]
        self.btn_retry = ctk.CTkButton(
            row, text="", fg_color=bg_color, hover_color=theme.SURFACE_2, text_color=text_color,
            command=self._retry_failures,
        )

        self.entry_query.bind("<Return>", lambda e: self._start_search())
        self.entry_query.bind("<KeyRelease>", self._on_query_change)

    def _build_progress_row(self, main: ctk.CTkFrame) -> None:
        row = ctk.CTkFrame(main, fg_color="transparent")
        row.pack(fill="x", pady=(4, 8))

        self.lbl_progress = ctk.CTkLabel(row, text="", anchor="w", text_color=theme.TEXT)
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
        self._confirm = Banner(main, theme.BG)
        self._confirm.pack(fill="x", pady=(0, 6))
        make_header(main, _COLS).pack(fill="x")
        self.scroll = ctk.CTkScrollableFrame(main)
        self.scroll.pack(fill="both", expand=True, pady=(2, 6))

    def _build_footer(self, main: ctk.CTkFrame) -> None:
        bar = ctk.CTkFrame(main, fg_color="transparent")
        bar.pack(fill="x", pady=(4, 0))

        stat = ctk.CTkFrame(bar, fg_color="transparent")
        stat.pack(side="left")

        self.chip_ok      = make_chip(stat, Tone.OK)
        self.chip_no_cte  = make_chip(stat, Tone.WARNING)
        self.chip_not_found = make_chip(stat, Tone.ERROR)
        self.chip_failed  = make_chip(stat, Tone.CONNECTION)
        self.chip_img_yes = make_chip(stat, Tone.INFO)
        self.chip_img_no  = make_chip(stat, Tone.NEUTRAL)
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

    def _rows(self) -> list[dict]:
        return list(self._results.values())

    def _failures(self) -> list[int]:
        return [n for n, r in self._results.items() if r["Status"] == CONNECTION_FAILED]

    def _reset_chips(self) -> None:
        self._set_chips(0, 0, 0, 0, 0, 0)

    def _update_chips(self) -> None:
        statuses = [r["Status"] for r in self._rows()]
        images   = [r.get("Imagem") for r in self._rows()]
        self._set_chips(
            statuses.count(SEARCH_OK), statuses.count(SEARCH_NO_CTE), statuses.count(SEARCH_NOT_FOUND),
            statuses.count(CONNECTION_FAILED), images.count("Sim"), images.count("Não"),
        )

    def _set_chips(self, ok: int, no_cte: int, not_found: int, failed: int, img_yes: int, img_no: int) -> None:
        self.chip_ok.configure(text=f"{ok}  Com CT-e")
        self.chip_no_cte.configure(text=f"{no_cte}  Sem CT-e")
        self.chip_not_found.configure(text=f"{not_found}  Não cadastrada")
        self.chip_failed.configure(text=f"{failed}  Falha de conexão")
        self.chip_img_yes.configure(text=f"{img_yes}  Com imagem")
        self.chip_img_no.configure(text=f"{img_no}  Sem imagem")

    def _update_retry_button(self) -> None:
        failures = self._failures()
        if failures and not self._searching:
            self.btn_retry.configure(text=f"Tentar de novo só essas ({len(failures)})")
            self.btn_retry.pack(side="left", padx=(12, 0))
        else:
            self.btn_retry.pack_forget()

    def _insert_row(self, parent, r: dict, number: int | None = None, before=None) -> None:
        if number is None:
            self._row_count += 1
            number = self._row_count
        texts = [str(number), str(r["NF-e"]), r["CT-e"], format_image(r.get("Imagem"))]
        row = insert_row(parent, number, _COLS, texts, r["Status"], search_tone(r["Status"]))
        if before is not None:
            row.pack_configure(before=before)
        self._row_widgets[r["NF-e"]] = (row, number)

    def _replace_row(self, r: dict) -> None:
        """Swap the widget of a retried invoice in place; redrawing the whole table costs seconds."""
        shown = self._row_widgets.get(r["NF-e"])
        if shown is None or not _FILTERS[self.option_filter.get()](r):
            self._redraw_table()  # visibility changed under an active filter (rare)
            return
        old_row, number = shown
        self._insert_row(self.scroll, r, number, before=old_row)
        old_row.destroy()

    def _clear_table(self) -> None:
        clear_scroll(self.scroll)
        self._results   = {}
        self._row_widgets = {}
        self._row_count = 0
        self._current_entry = None

    # ------------------------------------------------------------------
    # AÇÕES
    # ------------------------------------------------------------------

    def _back(self) -> None:
        self._stop_event.set()
        self._on_back()

    def _logout(self) -> None:
        self._stop_event.set()
        self._on_logout()

    def _on_query_change(self, _event=None) -> None:
        text = self.entry_query.get()
        # KeyRelease also fires for Enter, arrows and Shift: only react when the text really changed,
        # otherwise releasing the Enter that asked for confirmation would hide it right away.
        if text == self._last_query:
            return
        self._last_query = text
        parsed = parse_query(text)
        color = theme.STATUS[Tone.ERROR.value][0] if parsed.label and not parsed.valid else theme.TEXT_MUTED
        self.lbl_parse.configure(text=parsed.label, text_color=color)
        self._confirm.hide()  # a pending confirmation was for the old text

    def _start_search(self) -> None:
        if self._searching:
            return
        query = self.entry_query.get().strip()
        parsed = parse_query(query)
        self._on_query_change()
        if not parsed.valid:
            self.entry_query.focus()
            return
        if len(parsed.invoices) > CONFIRM_ABOVE:
            self._confirm.show(
                Tone.INFO, f"Consultar {parsed.label.split(' · ')[-1]}? Pode levar alguns minutos.",
                [("Consultar", lambda: self._begin_search(query, parsed.invoices)), ("Cancelar", self._confirm.hide)],
            )
            return
        self._begin_search(query, parsed.invoices)

    def _begin_search(self, query: str, invoices: list[int]) -> None:
        if self._searching:  # "Consultar" on the banner while a retry is already running
            return
        self._clear_table()
        self.option_filter.set("Todos")
        self._reset_chips()
        self._run(invoices, query, retry=False)

    def _retry_failures(self) -> None:
        if self._searching or self._current_entry is None:
            return
        failures = self._failures()
        if failures:
            self._run(failures, self._current_entry["query"], retry=True)

    def _run(self, invoices: list[int], query: str, retry: bool) -> None:
        self._confirm.hide()
        self._searching = True
        self._stop_event.clear()
        set_message(self.lbl_progress, "")
        self.progressbar.set(0)
        self.btn_clear.configure(state="disabled")
        self.btn_export.configure(state="disabled")
        self._update_retry_button()
        self._btn_search_style = show_cancel(self.btn_search, self._cancel)

        def finish(**kwargs):
            return lambda *_: self._finish(query, retry=retry, **kwargs)

        worker = SearchWorker(
            session=self._session,
            invoices=invoices,
            stop_event=self._stop_event,
            after_fn=self.after,
            callbacks=SearchCallbacks(
                on_row=self._add_row,
                on_notice=lambda text: set_message(self.lbl_progress, text, Tone.WARNING),
                on_done=finish(),
                on_cancel=finish(cancelled=True),
                on_session_lost=finish(session_lost=True),
            ),
            relogin=self._relogin,
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
        self._row_widgets = {}
        self._row_count = 0
        predicate = _FILTERS[self.option_filter.get()]
        for r in self._rows():
            if predicate(r):
                self._insert_row(self.scroll, r)

    # ------------------------------------------------------------------
    # ATUALIZAÇÃO DA TABELA
    # ------------------------------------------------------------------

    def _add_row(self, r: dict, prog: float, current: int, total: int, elapsed: float) -> None:
        self.progressbar.set(prog)
        m, s = divmod(int(elapsed), 60)
        set_message(self.lbl_progress, f"NF-e {r['NF-e']}  ({current}/{total})  {m:02d}:{s:02d}")
        retried = r["NF-e"] in self._results
        self._results[r["NF-e"]] = r
        if retried:
            self._replace_row(r)
        elif _FILTERS[self.option_filter.get()](r):
            self._insert_row(self.scroll, r)
        self._update_chips()

    # ------------------------------------------------------------------
    # FINALIZAÇÃO
    # ------------------------------------------------------------------

    def _finish(self, query: str, retry: bool, cancelled: bool = False, session_lost: bool = False) -> None:
        self._searching = False
        restore_button(self.btn_search, self._btn_search_style)
        self.btn_search.configure(state="normal")
        self.btn_clear.configure(state="normal")

        if session_lost:
            set_message(self.lbl_progress, "Sessão expirada. Saia e entre de novo.", Tone.ERROR)
        elif cancelled:
            set_message(self.lbl_progress, "Busca cancelada.")
        else:
            self.progressbar.set(1)
            failures = self._failures()
            if failures:
                set_message(
                    self.lbl_progress, f"Consulta concluída com {len(failures)} falha(s) de conexão.", Tone.CONNECTION,
                )
            else:
                set_message(self.lbl_progress, "Consulta concluída.")

        self._update_chips()
        self._update_retry_button()
        if self._results:
            self.btn_export.configure(state="normal")
            self._save_history(query, update=retry)

    # ------------------------------------------------------------------
    # LIMPAR
    # ------------------------------------------------------------------

    def _clear(self) -> None:
        self.entry_query.delete(0, "end")
        self._on_query_change()
        self._confirm.hide()
        self._clear_table()
        set_message(self.lbl_progress, "")
        self.progressbar.set(0)
        self.option_filter.set("Todos")
        self._reset_chips()
        self._update_retry_button()
        self.btn_export.configure(state="disabled")
        self.entry_query.focus()

    # ------------------------------------------------------------------
    # EXPORTAR EXCEL
    # ------------------------------------------------------------------

    def _export(self) -> None:
        if not self._results:
            return
        filename = export_excel(self._rows())
        set_message(self.lbl_progress, f"Salvo: {filename}", Tone.OK)

    # ------------------------------------------------------------------
    # HISTÓRICO
    # ------------------------------------------------------------------

    def _history_label(self, hour: str, query: str) -> str:
        text = " ".join(query.split())  # a pasted Excel column becomes one line
        if len(text) > _HISTORY_QUERY_CHARS:
            text = text[:_HISTORY_QUERY_CHARS - 1] + "…"
        count = len(self._results)
        label = f"{hour}  ·  {text}  ({count} {'item' if count == 1 else 'itens'})"
        failures = len(self._failures())
        return f"{label}  ·  {failures} com falha" if failures else label

    def _save_history(self, query: str, update: bool) -> None:
        """A new search adds an entry; retrying its failures updates that same entry."""
        if update and self._current_entry is not None:
            entry = self._current_entry
            entry["results"] = self._rows()
            entry["label"] = self._history_label(entry["hour"], entry["query"])
            self._hist.refresh()
            return
        hour = datetime.now().strftime("%H:%M")
        entry = {"hour": hour, "query": query, "results": self._rows()}
        entry["label"] = self._history_label(hour, query)
        self._current_entry = entry
        self._hist.add(entry)

    def _restore(self, entry: dict) -> None:
        if self._searching:
            return
        self.entry_query.delete(0, "end")
        self.entry_query.insert(0, entry["query"])
        self._on_query_change()
        self._confirm.hide()

        self._clear_table()
        self._results = {r["NF-e"]: r for r in entry["results"]}
        self._current_entry = entry
        self.option_filter.set("Todos")
        self._redraw_table()
        self.scroll._parent_canvas.yview_moveto(0)

        self._update_chips()
        self._update_retry_button()
        set_message(self.lbl_progress, f"Histórico: {entry['label']}")
        self.progressbar.set(1)
        self.btn_export.configure(state="normal")
