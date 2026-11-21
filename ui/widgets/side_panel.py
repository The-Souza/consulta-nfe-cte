import tkinter
from typing import Callable

import customtkinter as ctk

from ui import theme
from ui.widgets.scrollbar import hide_frame_scrollbar_when_idle, use_theme_width
from utils.search_results import NO_DRIVER, NO_DRIVER_LABEL, DriverGroup
from utils.status import Tone

MAX_ITEMS = 50  # a query can have many CT-es; the panel shows the largest ones
_WIDTH = 300
_DETAIL_WRAP = _WIDTH - 60  # item padding, list padding and the scrollbar
_TITLE_CHARS = 22  # a CTkLabel can't ellipsize: longer driver names are cut by hand, clear of the count

CTE_TAB = "cte"
DRIVERS_TAB = "drivers"
_TAB_NAMES = {CTE_TAB: "CT-es", DRIVERS_TAB: "Motoristas"}


def _divider(parent) -> tkinter.Frame:
    """1 px line. A CTkFrame of height 1 isn't drawn (its rounded canvas needs more room)."""
    return tkinter.Frame(parent, height=1, bg=theme.BORDER, bd=0, highlightthickness=0)


def _plural(n: int, singular: str, plural: str) -> str:
    return f"{n:,}".replace(",", ".") + " " + (singular if n == 1 else plural)


def _short(text: str) -> str:
    return text if len(text) <= _TITLE_CHARS else text[:_TITLE_CHARS - 1].rstrip() + "…"


class _PanelItem(ctk.CTkFrame):
    """One clickable line of the panel: title, count, an optional detail line and a proportional bar.
    The same widget serves both tabs, so switching tabs reuses it instead of creating new ones."""

    def __init__(self, parent, fonts: dict[str, ctk.CTkFont], on_click: Callable[[str], None]):
        super().__init__(parent, fg_color=theme.TRANSPARENT, corner_radius=theme.RADIUS_INPUT, border_width=1,
                         border_color=theme.SURFACE)
        self._fonts = fonts
        self._key = ""
        # What is on screen, so an update only touches what changed (every CTk configure redraws)
        self._shown: dict[str, object] = {}
        top = ctk.CTkFrame(self, fg_color=theme.TRANSPARENT)
        top.pack(fill="x", padx=theme.SPACE_MD, pady=(theme.SPACE_SM + 2, theme.SPACE_XS + 2))
        self._title = ctk.CTkLabel(top, text="", text_color=theme.TEXT, height=18, font=fonts["cte"])
        self._title.pack(side="left")
        self._count = ctk.CTkLabel(top, text="", text_color=theme.TEXT_LABEL, height=18,
                                   font=theme.font(theme.FONT_SIZE_SM))
        self._count.pack(side="right")
        # Many delivery days don't fit in one line: wrap instead of cutting the last dates off
        self._detail = ctk.CTkLabel(self, text="", text_color=theme.TEXT_MUTED, height=16, anchor="w", justify="left",
                                    font=theme.font(theme.FONT_SIZE_SM, mono=True), wraplength=_DETAIL_WRAP)
        self._bar = ctk.CTkProgressBar(self, height=6, corner_radius=3, fg_color=theme.SURFACE_2)
        self._bar.pack(fill="x", padx=theme.SPACE_MD, pady=(0, theme.SPACE_SM + 2))

        for widget in (self, top, self._title, self._count, self._detail, self._bar):
            widget.bind("<Button-1>", lambda _e: on_click(self._key))
            widget.configure(cursor="hand2")

    def _changed(self, name: str, value) -> bool:
        if self._shown.get(name, object()) == value:
            return False
        self._shown[name] = value
        return True

    def update_item(self, key: str, title: str, style: str, count: str, detail: str, ratio: float,
                    selected: bool) -> None:
        """style: "cte" (mono), "driver" or "unknown" (italic, muted: invoices outside the sheet)."""
        self._key = key
        if self._changed("title", title):
            self._title.configure(text=title)
        if self._changed("style", style):
            self._title.configure(font=self._fonts[style],
                                  text_color=theme.TEXT_MUTED if style == "unknown" else theme.TEXT)
        if self._changed("count", count):
            self._count.configure(text=count)
        if self._changed("detail", detail):
            self._detail.configure(text=detail)
            if detail:
                self._detail.pack(fill="x", padx=theme.SPACE_MD, pady=(0, theme.SPACE_XS + 2), before=self._bar)
            else:
                self._detail.pack_forget()
        if self._changed("ratio", ratio):
            self._bar.set(ratio)
        if self._changed("selected", selected):
            ok_text, ok_bg = theme.STATUS[Tone.OK.value]
            self.configure(fg_color=ok_bg if selected else theme.TRANSPARENT,
                           border_color=theme.SELECTED_BORDER if selected else theme.SURFACE)
            self._bar.configure(progress_color=ok_text if selected else theme.PANEL_BAR)


class SidePanel(ctk.CTkFrame):
    """Side panel with two tabs: 'CT-es' and 'Motoristas'. Clicking an item reports it (or None when it
    was already selected); the CT-e footer link reports the invoices without CT-e. Item widgets are reused
    between updates, because creating hundreds of CTk widgets on every refresh would freeze the screen."""

    def __init__(
        self,
        parent,
        on_pick_cte: Callable[[str | None], None],
        on_pick_no_cte: Callable[[], None],
        on_pick_driver: Callable[[str | None], None],
        on_tab: Callable[[str], None],
    ):
        super().__init__(parent, width=_WIDTH, fg_color=theme.SURFACE, border_color=theme.BORDER, border_width=1,
                         corner_radius=theme.RADIUS_CARD)
        self.pack_propagate(False)
        self._on_pick_cte = on_pick_cte
        self._on_pick_driver = on_pick_driver
        self._on_tab = on_tab
        self._tab = CTE_TAB
        self._preferred_tab = CTE_TAB  # last tab the user picked; shown again when the drivers tab returns
        self._selected_cte: str | None = None
        self._selected_driver: str | None = None
        self._ctes: list[tuple[str, int]] = []
        self._drivers: list[DriverGroup] = []
        self._items: list[_PanelItem] = []
        self._fonts = {
            "cte": theme.font(theme.FONT_SIZE_INPUT, "bold", mono=True),
            "driver": theme.font(theme.FONT_SIZE_INPUT, "bold"),
            "unknown": ctk.CTkFont(family=theme.FONT_FAMILY, size=theme.FONT_SIZE_INPUT, slant="italic"),
        }

        self._build_tabs()
        self._build_header()
        # Packed before the list so the list takes the remaining height; holds the active tab's footer.
        # A plain Frame shrinks to its content (an empty CTkFrame asks for 200 px).
        self._footer_slot = tkinter.Frame(self, bg=theme.SURFACE, bd=0, highlightthickness=0)
        self._footer_slot.pack(side="bottom", fill="x", padx=1, pady=(0, theme.SPACE_XS))
        self._list = ctk.CTkScrollableFrame(
            self, fg_color=theme.TRANSPARENT, scrollbar_button_color=theme.SCROLLBAR_BUTTON,
            scrollbar_button_hover_color=theme.SCROLLBAR_BUTTON_HOVER,
        )
        self._list.pack(fill="both", expand=True, padx=theme.SPACE_XS, pady=theme.SPACE_XS)
        hide_frame_scrollbar_when_idle(self._list)
        use_theme_width(self._list)
        self._more = ctk.CTkLabel(self._list, text="", text_color=theme.TEXT_MUTED, font=theme.font(theme.FONT_SIZE_SM))
        self._empty = ctk.CTkLabel(self._list, text="", text_color=theme.TEXT_MUTED, font=theme.font(theme.FONT_SIZE_SM))
        self._cte_footer = self._build_cte_footer(on_pick_no_cte)
        self._drivers_footer = self._build_drivers_footer()
        self._apply_tab()

    # ------------------------------------------------------------------
    # LAYOUT
    # ------------------------------------------------------------------

    def _build_tabs(self) -> None:
        self._tabs_row = ctk.CTkFrame(self, fg_color=theme.TRANSPARENT)
        self._tabs = ctk.CTkSegmentedButton(
            self._tabs_row, values=list(_TAB_NAMES.values()), command=self._on_tab_click, height=30,
            corner_radius=theme.RADIUS_INPUT, font=theme.font(theme.FONT_SIZE_BODY), fg_color=theme.BG,
            selected_color=theme.SURFACE_2, selected_hover_color=theme.SURFACE_2, unselected_color=theme.BG,
            unselected_hover_color=theme.SURFACE, text_color=theme.TEXT,
        )
        self._tabs.pack(fill="x")
        self._tabs.set(_TAB_NAMES[CTE_TAB])
        # Shown only when the drivers lookup is on (see show_drivers_tab)

    def _build_header(self) -> None:
        self._header = ctk.CTkFrame(self, fg_color=theme.TRANSPARENT)
        self._header.pack(fill="x", padx=theme.SPACE_LG, pady=(theme.SPACE_MD + 2, theme.SPACE_SM))
        top = ctk.CTkFrame(self._header, fg_color=theme.TRANSPARENT)
        top.pack(fill="x")
        self._title = ctk.CTkLabel(top, text="", text_color=theme.TEXT, height=20,
                                   font=theme.font(theme.FONT_SIZE_INPUT, "bold"))
        self._title.pack(side="left")
        self._distinct = ctk.CTkLabel(top, text="", text_color=theme.TEXT_MUTED, height=20,
                                      font=theme.font(theme.FONT_SIZE_SM))
        self._distinct.pack(side="right")
        self._hint = ctk.CTkLabel(self._header, text="", text_color=theme.TEXT_MUTED, height=18, anchor="w",
                                  font=theme.font(theme.FONT_SIZE_SM))
        self._hint.pack(fill="x")
        _divider(self).pack(fill="x", padx=1)

    def _build_cte_footer(self, on_pick_no_cte: Callable[[], None]) -> ctk.CTkFrame:
        container = ctk.CTkFrame(self._footer_slot, fg_color=theme.SURFACE)
        _divider(container).pack(fill="x")
        footer = ctk.CTkFrame(container, fg_color=theme.TRANSPARENT)
        footer.pack(fill="x", padx=theme.SPACE_LG, pady=theme.SPACE_MD)

        with_row = ctk.CTkFrame(footer, fg_color=theme.TRANSPARENT)
        with_row.pack(fill="x", pady=(0, theme.SPACE_SM))
        ctk.CTkLabel(with_row, text="NF-es com CT-e", text_color=theme.TEXT_MUTED, height=18,
                     font=theme.font(theme.FONT_SIZE_BODY)).pack(side="left")
        self._with_cte = ctk.CTkLabel(with_row, text="0", text_color=theme.TEXT, height=18,
                                      font=theme.font(theme.FONT_SIZE_BODY, mono=True))
        self._with_cte.pack(side="right")

        warning = theme.STATUS[Tone.WARNING.value][0]
        without_row = ctk.CTkFrame(footer, fg_color=theme.TRANSPARENT, cursor="hand2")
        without_row.pack(fill="x")
        link = ctk.CTkLabel(without_row, text="NF-es sem CT-e", text_color=warning, height=18, cursor="hand2",
                            font=ctk.CTkFont(family=theme.FONT_FAMILY, size=theme.FONT_SIZE_BODY, underline=True))
        link.pack(side="left")
        self._without_cte = ctk.CTkLabel(without_row, text="0", text_color=warning, height=18, cursor="hand2",
                                         font=theme.font(theme.FONT_SIZE_BODY, mono=True))
        self._without_cte.pack(side="right")
        for widget in (without_row, link, self._without_cte):
            widget.bind("<Button-1>", lambda _e: on_pick_no_cte())
        return container

    def _build_drivers_footer(self) -> ctk.CTkFrame:
        container = ctk.CTkFrame(self._footer_slot, fg_color=theme.SURFACE)
        _divider(container).pack(fill="x")
        ctk.CTkLabel(
            container, text="Sem foto no sistema? A data diz em qual lote de canhotos físicos procurar.",
            text_color=theme.TEXT_MUTED, font=theme.font(theme.FONT_SIZE_SM), justify="left", anchor="w",
            wraplength=_WIDTH - 2 * theme.SPACE_LG,
        ).pack(fill="x", padx=theme.SPACE_LG, pady=theme.SPACE_MD)
        return container

    # ------------------------------------------------------------------
    # API
    # ------------------------------------------------------------------

    @property
    def tab(self) -> str:
        return self._tab

    def show_drivers_tab(self, visible: bool) -> None:
        """The Motoristas tab only exists while there is a drivers lookup. It hides at every new search
        until the lookup arrives, so the tab the user picked is remembered and comes back with it."""
        if visible:
            if not self._tabs_row.winfo_manager():
                self._tabs_row.pack(fill="x", padx=theme.SPACE_MD, pady=(theme.SPACE_MD, 0), before=self._header)
            self._switch(self._preferred_tab)
        else:
            self._tabs_row.pack_forget()
            self._switch(CTE_TAB)

    def show_tab(self, tab: str) -> None:
        self._preferred_tab = tab
        self._switch(tab)

    def update_counts(self, ctes: list[tuple[str, int]], drivers: list[DriverGroup], with_cte: int,
                      without_cte: int) -> None:
        """ctes: (CT-e, invoices) and drivers already sorted, most invoices first."""
        self._ctes = ctes
        self._drivers = drivers
        self._with_cte.configure(text=f"{with_cte:,}".replace(",", "."))
        self._without_cte.configure(text=f"{without_cte:,}".replace(",", "."))
        self._update_header_count()
        self._render()

    def select_cte(self, cte: str | None) -> None:
        self._selected_cte = cte
        if self._tab == CTE_TAB:
            self._render()

    def select_driver(self, driver: str | None) -> None:
        self._selected_driver = driver
        if self._tab == DRIVERS_TAB:
            self._render()

    # ------------------------------------------------------------------

    def _on_tab_click(self, name: str) -> None:
        tab = next(key for key, label in _TAB_NAMES.items() if label == name)
        self._preferred_tab = tab
        if tab != self._tab:
            self._switch(tab)
            self._on_tab(tab)

    def _switch(self, tab: str) -> None:
        if tab == self._tab:
            return
        self._tab = tab
        self._tabs.set(_TAB_NAMES[tab])
        self._apply_tab()

    def _apply_tab(self) -> None:
        is_cte = self._tab == CTE_TAB
        self._title.configure(text="CT-es nesta consulta" if is_cte else "Motoristas nesta consulta")
        self._hint.configure(
            text="Clique em um CT-e para filtrar a tabela" if is_cte else "Clique em um motorista para filtrar a tabela",
        )
        self._empty.configure(text="Nenhum CT-e nesta consulta." if is_cte else "Nenhuma NF-e nesta consulta.")
        shown, hidden = (self._cte_footer, self._drivers_footer) if is_cte else (self._drivers_footer, self._cte_footer)
        hidden.pack_forget()
        shown.pack(fill="x")
        self._update_header_count()
        self._render()

    def _update_header_count(self) -> None:
        if self._tab == CTE_TAB:
            text = _plural(len(self._ctes), "distinto", "distintos")
        else:
            known = sum(1 for g in self._drivers if g.driver != NO_DRIVER)
            text = _plural(known, "motorista", "motoristas")
        self._distinct.configure(text=text)

    def _entries(self) -> list[tuple[str, str, str, int, str, bool]]:
        """(key, title, style, count, detail, selected) of the active tab."""
        if self._tab == CTE_TAB:
            return [(cte, cte, "cte", count, "", cte == self._selected_cte) for cte, count in self._ctes]
        entries = []
        for group in self._drivers:
            unknown = group.driver == NO_DRIVER
            dates = " · ".join(day.strftime("%d/%m") for day in group.dates)
            entries.append((
                group.driver, NO_DRIVER_LABEL if unknown else _short(group.driver), "unknown" if unknown else "driver",
                group.count, f"Entregas: {dates}" if dates else "", group.driver == self._selected_driver,
            ))
        return entries

    def _render(self) -> None:
        entries = self._entries()
        shown = entries[:MAX_ITEMS]
        largest = max((count for _, _, _, count, _, _ in shown), default=1)

        while len(self._items) < len(shown):
            self._items.append(_PanelItem(self._list, self._fonts, self._click))
        for index, item in enumerate(self._items):
            if index < len(shown):
                key, title, style, count, detail, selected = shown[index]
                item.update_item(key, title, style, _plural(count, "NF-e", "NF-es"), detail, count / largest, selected)
                if not item.winfo_manager():
                    item.pack(fill="x", pady=(0, theme.SPACE_XS), before=self._more if self._more.winfo_manager() else None)
            elif item.winfo_manager():
                item.pack_forget()

        hidden = len(entries) - len(shown)
        if hidden > 0:
            noun = ("CT-e", "CT-es") if self._tab == CTE_TAB else ("motorista", "motoristas")
            self._more.configure(text=f"e mais {_plural(hidden, *noun)}")
            self._more.pack(pady=theme.SPACE_SM)
        else:
            self._more.pack_forget()
        if entries:
            self._empty.pack_forget()
        else:
            self._empty.pack(pady=theme.SPACE_XL)

    def _click(self, key: str) -> None:
        if self._tab == CTE_TAB:
            self._on_pick_cte(None if key == self._selected_cte else key)
        else:
            self._on_pick_driver(None if key == self._selected_driver else key)
