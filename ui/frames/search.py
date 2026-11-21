import threading
from datetime import datetime
from typing import Callable

import customtkinter as ctk

from drivers import DriverLookup, sheet_status
from ui import theme
from ui.icons import get_icon
from ui.widgets.banner import Banner
from ui.widgets.buttons import restore_button, show_cancel
from ui.widgets.cte_panel import CtePanel
from ui.widgets.filter_chips import FilterChips
from ui.widgets.history import HistoryPanel
from ui.widgets.progress import set_message
from ui.widgets.results_table import ResultsTable
from ui.widgets.topbar import make_topbar
from ui.workers.search import SearchCallbacks, SearchWorker
from utils.excel import export_excel
from utils.nfe_query import parse_query
from utils.search_results import chip_counts, cte_counts, cte_multiplicity, status_text, visible_rows
from utils.status import CONNECTION_FAILED, Tone

_HISTORY_QUERY_CHARS = 40
_COUNTS_INTERVAL_MS = 250
_EMPTY_FILTER = "Nenhuma NF-e neste filtro."


def _primary_button(parent, text: str, icon: str, command: Callable, **options) -> ctk.CTkButton:
    return ctk.CTkButton(
        parent, text=text, image=get_icon(icon, 16, theme.TEXT_ON_PRIMARY), compound="left", height=38,
        corner_radius=theme.RADIUS_INPUT, fg_color=theme.PRIMARY, hover_color=theme.PRIMARY_HOVER,
        text_color=theme.TEXT_ON_PRIMARY, font=theme.font(theme.FONT_SIZE_INPUT, "bold"), command=command,
        **options,
    )


class SearchFrame(ctk.CTkFrame):
    def __init__(self, parent, session, user_name, on_logout, on_back=None, relogin: Callable[[], None] | None = None):
        super().__init__(parent, fg_color=theme.BG, corner_radius=0)
        self._session    = session
        self._relogin    = relogin
        self._on_logout  = on_logout
        self._on_back    = on_back
        self._results: dict[int, dict] = {}  # NF-e -> row, in query order
        self._chip = "all"
        self._cte: str | None = None  # CT-e picked in the side panel; takes precedence over the chip
        self._multiplicity: dict[str, int] = {}
        self._current_entry: dict | None = None  # history entry of the results on screen
        self._drivers: DriverLookup | None = None  # Supabase lookup of the results on screen
        self._searching  = False
        self._elapsed    = 0.0
        self._elapsed_before = 0.0
        self._counts_job: str | None = None  # pending chip refresh (after id)
        self._stop_event = threading.Event()
        self._btn_search_style: dict = {}
        self._last_query: str | None = None  # field text the parse label was computed for
        self._build(user_name)

    # ------------------------------------------------------------------
    # LAYOUT
    # ------------------------------------------------------------------

    def _build(self, user_name: str) -> None:
        make_topbar(self, "Consulta NF-e / CT-e", user_name, self._logout,
                    on_back=self._back if self._on_back else None)
        main = ctk.CTkFrame(self, fg_color=theme.TRANSPARENT)
        main.pack(fill="both", expand=True, padx=20, pady=(theme.SPACE_LG, 14))
        self._build_search_row(main)
        chips_row = ctk.CTkFrame(main, fg_color=theme.TRANSPARENT)
        chips_row.pack(fill="x", pady=(theme.SPACE_MD, 0))
        self.chips = FilterChips(chips_row, on_pick=self._on_chip)
        self.chips.pack(side="left", fill="x", expand=True)
        # Packed on the right only while there is something to say (see _show_sheet_status)
        self.lbl_sheet = ctk.CTkLabel(
            chips_row, text="", compound="left", font=theme.font(theme.FONT_SIZE_SM), text_color=theme.TEXT_MUTED,
        )
        self._build_footer(main)  # packed before the card so the card takes the remaining height
        self._build_card(main)

    def _build_search_row(self, main: ctk.CTkFrame) -> None:
        row = ctk.CTkFrame(main, fg_color=theme.TRANSPARENT)
        row.pack(fill="x")

        field = ctk.CTkFrame(row, fg_color=theme.TRANSPARENT)
        field.pack(side="left", padx=(0, theme.SPACE_MD))
        labels = ctk.CTkFrame(field, fg_color=theme.TRANSPARENT)
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
        self.entry_query.bind("<Return>", lambda e: self._start_search())
        self.entry_query.bind("<KeyRelease>", self._on_query_change)

        self.btn_search = _primary_button(row, "Buscar", "search", self._start_search, width=110)
        self.btn_search.pack(side="left", padx=(0, theme.SPACE_SM), anchor="s")
        self.btn_clear = ctk.CTkButton(
            row, text="Limpar", width=90, height=38, corner_radius=theme.RADIUS_INPUT,
            fg_color=theme.TRANSPARENT, hover_color=theme.SURFACE_2, border_width=1, border_color=theme.BORDER_INPUT,
            text_color=theme.TEXT, font=theme.font(theme.FONT_SIZE_INPUT), command=self._clear,
        )
        self.btn_clear.pack(side="left", anchor="s")

        status = ctk.CTkFrame(row, fg_color=theme.TRANSPARENT, width=360)
        status.pack(side="right", anchor="s", pady=(0, theme.SPACE_XS))
        self.lbl_progress = ctk.CTkLabel(
            status, text="", anchor="e", text_color=theme.TEXT_MUTED, font=theme.font(theme.FONT_SIZE_BODY),
        )
        self.lbl_progress.pack(fill="x")
        self.progressbar = ctk.CTkProgressBar(
            status, width=360, height=4, corner_radius=2, fg_color=theme.TOPBAR_BORDER, progress_color=theme.PROGRESS,
        )
        self.progressbar.pack(pady=(theme.SPACE_XS, 0))
        self.progressbar.set(0)

    def _build_card(self, main: ctk.CTkFrame) -> None:
        content = ctk.CTkFrame(main, fg_color=theme.TRANSPARENT)
        content.pack(fill="both", expand=True, pady=(theme.SPACE_MD, theme.SPACE_MD))
        self.panel = CtePanel(content, on_pick_cte=self._on_pick_cte, on_pick_no_cte=self._on_pick_no_cte)
        self.panel.pack(side="right", fill="y", padx=(theme.SPACE_LG, 0))
        card = ctk.CTkFrame(
            content, fg_color=theme.SURFACE, border_color=theme.BORDER, border_width=1, corner_radius=theme.RADIUS_CARD,
        )
        card.pack(side="left", fill="both", expand=True)
        inner = ctk.CTkFrame(card, fg_color=theme.SURFACE, corner_radius=0)
        inner.pack(fill="both", expand=True, padx=1, pady=theme.SPACE_SM)
        self._conn_banner = Banner(inner, theme.SURFACE)
        self._conn_banner.pack(fill="x")
        self._retry_banner = Banner(inner, theme.SURFACE)
        self._retry_banner.pack(fill="x")
        self._filter_banner = Banner(inner, theme.SURFACE)
        self._filter_banner.pack(fill="x")
        self.table = ResultsTable(inner)
        self.table.pack(fill="both", expand=True)

    def _build_footer(self, main: ctk.CTkFrame) -> None:
        bar = ctk.CTkFrame(main, fg_color=theme.TRANSPARENT)
        bar.pack(side="bottom", fill="x")
        self.btn_export = _primary_button(bar, "Exportar Excel", "download", self._export, state="disabled")
        self.btn_export.pack(side="right", anchor="n")
        ctk.CTkLabel(
            bar, text="Inclui a aba “Resumo CT-e”", text_color=theme.TEXT_MUTED, font=theme.font(theme.FONT_SIZE_SM),
        ).pack(side="right", anchor="n", padx=(0, theme.SPACE_MD), pady=(theme.SPACE_SM + 2, 0))
        history = ctk.CTkFrame(bar, fg_color=theme.TRANSPARENT)
        history.pack(side="left", fill="x", expand=True, padx=(0, theme.SPACE_LG))
        self._hist = HistoryPanel(history, on_restore=self._restore)

    # ------------------------------------------------------------------
    # TABELA E FILTROS
    # ------------------------------------------------------------------

    def _rows(self) -> list[dict]:
        return list(self._results.values())

    def _failures(self) -> list[int]:
        return [n for n, r in self._results.items() if r["Status"] == CONNECTION_FAILED]

    def _render(self) -> None:
        """Redraw the table for the active filter (the Treeview handles hundreds of rows quickly)."""
        rows = visible_rows(self._rows(), self._chip, self._cte)
        self.table.show(rows, self._multiplicity, _EMPTY_FILTER if self._results else "")

    def _on_chip(self, key: str) -> None:
        self._chip = key
        self._set_cte(None)
        self.chips.set_active(key)
        self._render()

    def _on_pick_no_cte(self) -> None:
        """'NF-es sem CT-e' link in the panel: same as the chip, so it does nothing when the count is 0."""
        if chip_counts(self._rows())["no_cte"]:
            self._on_chip("no_cte")

    def _on_pick_cte(self, cte: str | None) -> None:
        """Click in the side panel: filter the table by that CT-e, or clear it (same CT-e again).
        Picking a CT-e resets the chip to "Todos", so clearing the CT-e shows every invoice again."""
        if cte is not None:
            self._chip = "all"
        self._set_cte(cte)
        self.chips.set_active(None if cte else self._chip)
        self._render()

    def _set_cte(self, cte: str | None) -> None:
        changed = cte != self._cte
        self._cte = cte
        self.panel.select(cte)
        if cte is None:
            self._filter_banner.hide()
            return
        count = self._multiplicity.get(cte, 0)
        text = f"Mostrando as {count} NF-es do CT-e {cte}" if count != 1 else f"Mostrando 1 NF-e do CT-e {cte}"
        if changed or not self._filter_banner.visible:
            self._filter_banner.show(
                Tone.OK, text, [("Limpar filtro", lambda: self._on_pick_cte(None))], icon="funnel", filled=False,
            )
        else:
            self._filter_banner.set_text(text)  # same CT-e, new count: don't rebuild the banner

    def _update_counts(self) -> None:
        """Chips and side panel. Called directly when something changed at once, or by the throttle."""
        if self._counts_job is not None:
            self.after_cancel(self._counts_job)
            self._counts_job = None
        rows = self._rows()
        counts = chip_counts(rows)
        self.chips.set_counts(counts)
        self.panel.update_counts(
            cte_counts(rows), with_cte=sum(self._multiplicity.values()), without_cte=counts["no_cte"],
        )
        if self._cte is not None:
            self._set_cte(self._cte)  # rows of the picked CT-e may have arrived: keep the banner count right

    def destroy(self) -> None:
        if self._counts_job is not None:  # Voltar/Sair during a search
            self.after_cancel(self._counts_job)
            self._counts_job = None
        super().destroy()

    def _schedule_counts(self) -> None:
        """During a search, refresh the chips at most every 250 ms instead of on every row."""
        if self._counts_job is None:
            self._counts_job = self.after(_COUNTS_INTERVAL_MS, self._update_counts)

    def _reset_view(self) -> None:
        self._results = {}
        self._multiplicity = {}
        self._drivers = None
        self._show_sheet_status()
        self._chip = "all"
        self._set_cte(None)
        self.chips.set_active("all")
        self._update_counts()
        self.table.clear()
        self._conn_banner.hide()
        self._retry_banner.hide()

    # ------------------------------------------------------------------
    # BUSCA
    # ------------------------------------------------------------------

    def _back(self) -> None:
        self._stop_event.set()
        self._on_back()

    def _logout(self) -> None:
        self._stop_event.set()
        self._on_logout()

    def _on_query_change(self, _event=None) -> None:
        text = self.entry_query.get()
        # KeyRelease also fires for Enter, arrows and Shift: only parse again when the text really changed.
        if text == self._last_query:
            return
        self._last_query = text
        parsed = parse_query(text)
        color = theme.STATUS[Tone.ERROR.value][0] if parsed.label and not parsed.valid else theme.TEXT_MUTED
        self.lbl_parse.configure(text=parsed.label, text_color=color)

    def _start_search(self) -> None:
        if self._searching:
            return
        query = self.entry_query.get().strip()
        parsed = parse_query(query)
        self._on_query_change()
        if not parsed.valid:
            self.entry_query.focus()
            return
        self._current_entry = None
        self._reset_view()
        self._run(parsed.invoices, query, retry=False)

    def _retry_failures(self) -> None:
        if self._searching or self._current_entry is None:
            return
        failures = self._failures()
        if failures:
            self._conn_banner.hide()
            self._retry_banner.show(
                Tone.INFO, "Consultando de novo só as NF-es que falharam…", icon="rotate-cw",
            )
            self._run(failures, self._current_entry["query"], retry=True)

    def _run(self, invoices: list[int], query: str, retry: bool) -> None:
        self._elapsed_before = self._elapsed if retry else 0.0  # a retry adds to the search time
        self._searching = True
        self._stop_event.clear()
        set_message(self.lbl_progress, "")
        self.progressbar.set(0)
        self.btn_clear.configure(state="disabled")
        self.btn_export.configure(state="disabled")
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
                on_drivers=self._set_drivers,
            ),
            relogin=self._relogin,
            drivers=self._drivers if retry else None,
        )
        threading.Thread(target=worker.run, daemon=True).start()

    def _cancel(self) -> None:
        self._stop_event.set()

    def _set_drivers(self, lookup: DriverLookup) -> None:
        self._drivers = lookup
        self._show_sheet_status()

    def _show_sheet_status(self) -> None:
        status = sheet_status(self._drivers, datetime.now().astimezone())
        if status is None:
            self.lbl_sheet.pack_forget()
            return
        text, warning = status
        color = theme.STATUS[Tone.WARNING.value][0] if warning else theme.TEXT_MUTED
        self.lbl_sheet.configure(text=f" {text}", text_color=color, image=get_icon("cloud", 14, color))
        self.lbl_sheet.pack(side="right", before=self.chips)

    def _add_row(self, r: dict, prog: float, current: int, total: int, elapsed: float) -> None:
        self.progressbar.set(prog)
        self._elapsed = self._elapsed_before + elapsed
        m, s = divmod(int(self._elapsed), 60)
        set_message(self.lbl_progress, f"NF-e {r['NF-e']}  ({current}/{total})  {m:02d}:{s:02d}")

        retried = r["NF-e"] in self._results
        self._results[r["NF-e"]] = r
        multiplicity = cte_multiplicity(self._rows())
        # Rewrite the CT-e column only when a "×N" mark changed, not for every new CT-e seen once.
        repeated = {cte: n for cte, n in multiplicity.items() if n > 1}
        shared_cte = repeated != {cte: n for cte, n in self._multiplicity.items() if n > 1}
        self._multiplicity = multiplicity

        matches = bool(visible_rows([r], self._chip, self._cte))
        if retried:
            # Same invoice queried again: update its row in place, or redraw if it enters/leaves the filter.
            if not (matches and self.table.update_row(r, multiplicity)):
                self._render()
        elif matches:
            self.table.append(r, multiplicity)
        if shared_cte:
            self.table.refresh_multiplicity(multiplicity, self._results)
        self._schedule_counts()

    def _finish(self, query: str, retry: bool, cancelled: bool = False, session_lost: bool = False) -> None:
        self._searching = False
        restore_button(self.btn_search, self._btn_search_style)
        self.btn_search.configure(state="normal")
        self.btn_clear.configure(state="normal")
        self._retry_banner.hide()

        failures = self._failures()
        if session_lost:
            set_message(self.lbl_progress, "Sessão expirada. Saia e entre de novo.", Tone.ERROR)
        elif cancelled:
            set_message(self.lbl_progress, "Busca cancelada.")
        else:
            self.progressbar.set(1)
            set_message(self.lbl_progress, status_text(len(self._results), len(failures), self._elapsed))

        self._update_counts()
        if self._cte is not None:
            if self._cte not in self._multiplicity:  # its invoices changed CT-e on "Tentar de novo"
                self._on_pick_cte(None)
            else:
                self._set_cte(self._cte)  # the banner count may have changed
        elif self._chip != "all" and not chip_counts(self._rows())[self._chip]:
            self._on_chip("all")  # e.g. every failure was fixed by "Tentar de novo"
        self._show_connection_banner()
        if self._results:
            self.btn_export.configure(state="normal")
            self._save_history(query, update=retry)

    def _show_connection_banner(self) -> None:
        failures = len(self._failures())
        if not failures or self._searching:
            self._conn_banner.hide()
            return
        text = (f"{failures} NF-es não responderam" if failures > 1 else "1 NF-e não respondeu") + (
            " mesmo após 3 tentativas. As outras estão certas, não precisa buscar tudo de novo."
        )
        label = f"Tentar de novo só essas {failures}" if failures > 1 else "Tentar de novo só essa"
        self._conn_banner.show(Tone.CONNECTION, text, [(label, self._retry_failures)], icon="wifi-off")

    # ------------------------------------------------------------------
    # LIMPAR E EXPORTAR
    # ------------------------------------------------------------------

    def _clear(self) -> None:
        self.entry_query.delete(0, "end")
        self._on_query_change()
        self._current_entry = None
        self._reset_view()
        set_message(self.lbl_progress, "")
        self.progressbar.set(0)
        self.btn_export.configure(state="disabled")
        self.entry_query.focus()

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
            entry["drivers"] = self._drivers
            entry["label"] = self._history_label(entry["hour"], entry["query"])
            self._hist.refresh()
            return
        hour = datetime.now().strftime("%H:%M")
        entry = {"hour": hour, "query": query, "results": self._rows(), "drivers": self._drivers}
        entry["label"] = self._history_label(hour, query)
        self._current_entry = entry
        self._hist.add(entry)

    def _restore(self, entry: dict) -> None:
        if self._searching:
            return
        self.entry_query.delete(0, "end")
        self.entry_query.insert(0, entry["query"])
        self._on_query_change()

        self._reset_view()
        self._results = {r["NF-e"]: r for r in entry["results"]}
        self._multiplicity = cte_multiplicity(self._rows())
        self._drivers = entry["drivers"]
        self._show_sheet_status()
        self._current_entry = entry
        self._elapsed = 0.0  # the restored search's time isn't kept; a retry counts from zero
        self._render()
        self._update_counts()
        self._show_connection_banner()
        set_message(self.lbl_progress, f"Histórico: {entry['label']}")
        self.progressbar.set(1)
        self.btn_export.configure(state="normal")
