import tkinter
from typing import Callable

import customtkinter as ctk

from ui import theme
from ui.widgets.scrollbar import hide_frame_scrollbar_when_idle
from utils.status import Tone

MAX_ITEMS = 50  # a query can have thousands of CT-es; the panel shows the largest ones
_WIDTH = 300


def _divider(parent) -> tkinter.Frame:
    """1 px line. A CTkFrame of height 1 isn't drawn (its rounded canvas needs more room)."""
    return tkinter.Frame(parent, height=1, bg=theme.BORDER, bd=0, highlightthickness=0)


def _plural(n: int, singular: str, plural: str) -> str:
    return f"{n:,}".replace(",", ".") + " " + (singular if n == 1 else plural)


class _CteItem(ctk.CTkFrame):
    """One clickable line of the panel: CT-e, invoice count and a proportional bar."""

    def __init__(self, parent, on_click: Callable[[str], None]):
        super().__init__(parent, fg_color=theme.TRANSPARENT, corner_radius=theme.RADIUS_INPUT, border_width=1,
                         border_color=theme.SURFACE)
        self._cte = ""
        self._shown_count: int | None = None
        self._shown_ratio: float | None = None
        self._shown_selected: bool | None = None
        top = ctk.CTkFrame(self, fg_color=theme.TRANSPARENT)
        top.pack(fill="x", padx=theme.SPACE_MD, pady=(theme.SPACE_SM + 2, theme.SPACE_XS + 2))
        self._name = ctk.CTkLabel(top, text="", text_color=theme.TEXT, height=18,
                                  font=theme.font(theme.FONT_SIZE_INPUT, "bold", mono=True))
        self._name.pack(side="left")
        self._count = ctk.CTkLabel(top, text="", text_color=theme.TEXT_LABEL, height=18,
                                   font=theme.font(theme.FONT_SIZE_SM))
        self._count.pack(side="right")
        self._bar = ctk.CTkProgressBar(self, height=6, corner_radius=3, fg_color=theme.SURFACE_2)
        self._bar.pack(fill="x", padx=theme.SPACE_MD, pady=(0, theme.SPACE_SM + 2))

        for widget in (self, top, self._name, self._count, self._bar):
            widget.bind("<Button-1>", lambda _e: on_click(self._cte))
            widget.configure(cursor="hand2")

    def update_item(self, cte: str, count: int, largest: int, selected: bool) -> None:
        # Every CTk configure redraws the widget: only touch what changed, or a refresh of the whole
        # list costs half a second.
        if cte != self._cte:
            self._cte = cte
            self._name.configure(text=cte)
        if count != self._shown_count:
            self._shown_count = count
            self._count.configure(text=_plural(count, "NF-e", "NF-es"))
        ratio = count / largest
        if ratio != self._shown_ratio:
            self._shown_ratio = ratio
            self._bar.set(ratio)
        if selected != self._shown_selected:
            self._shown_selected = selected
            ok_text, ok_bg = theme.STATUS[Tone.OK.value]
            self.configure(fg_color=ok_bg if selected else theme.TRANSPARENT,
                           border_color=theme.SELECTED_BORDER if selected else theme.SURFACE)
            self._bar.configure(progress_color=ok_text if selected else theme.PANEL_BAR)


class CtePanel(ctk.CTkFrame):
    """Side panel 'CT-es nesta consulta'. Clicking a CT-e reports it (or None when it was already
    selected); the footer link reports the invoices without CT-e. Item widgets are reused between
    updates, because creating hundreds of CTk widgets on every refresh would freeze the screen."""

    def __init__(self, parent, on_pick_cte: Callable[[str | None], None], on_pick_no_cte: Callable[[], None]):
        super().__init__(parent, width=_WIDTH, fg_color=theme.SURFACE, border_color=theme.BORDER, border_width=1,
                         corner_radius=theme.RADIUS_CARD)
        self.pack_propagate(False)
        self._on_pick_cte = on_pick_cte
        self._selected: str | None = None
        self._counts: list[tuple[str, int]] = []
        self._items: list[_CteItem] = []
        self._build_header()
        self._build_footer(on_pick_no_cte)
        self._list = ctk.CTkScrollableFrame(
            self, fg_color=theme.TRANSPARENT, scrollbar_button_color=theme.SCROLLBAR_BUTTON,
            scrollbar_button_hover_color=theme.SCROLLBAR_BUTTON_HOVER,
        )
        self._list.pack(fill="both", expand=True, padx=theme.SPACE_XS, pady=theme.SPACE_XS)
        hide_frame_scrollbar_when_idle(self._list)
        self._more = ctk.CTkLabel(self._list, text="", text_color=theme.TEXT_MUTED, font=theme.font(theme.FONT_SIZE_SM))
        self._empty = ctk.CTkLabel(self._list, text="Nenhum CT-e nesta consulta.", text_color=theme.TEXT_MUTED,
                                   font=theme.font(theme.FONT_SIZE_SM))
        self._empty.pack(pady=theme.SPACE_XL)

    def _build_header(self) -> None:
        header = ctk.CTkFrame(self, fg_color=theme.TRANSPARENT)
        header.pack(fill="x", padx=theme.SPACE_LG, pady=(theme.SPACE_MD + 2, theme.SPACE_SM))
        top = ctk.CTkFrame(header, fg_color=theme.TRANSPARENT)
        top.pack(fill="x")
        ctk.CTkLabel(top, text="CT-es nesta consulta", text_color=theme.TEXT, height=20,
                     font=theme.font(theme.FONT_SIZE_INPUT, "bold")).pack(side="left")
        self._distinct = ctk.CTkLabel(top, text="", text_color=theme.TEXT_MUTED, height=20,
                                      font=theme.font(theme.FONT_SIZE_SM))
        self._distinct.pack(side="right")
        ctk.CTkLabel(header, text="Clique em um CT-e para filtrar a tabela", text_color=theme.TEXT_MUTED,
                     height=18, anchor="w", font=theme.font(theme.FONT_SIZE_SM)).pack(fill="x")
        _divider(self).pack(fill="x", padx=1)

    def _build_footer(self, on_pick_no_cte: Callable[[], None]) -> None:
        footer = ctk.CTkFrame(self, fg_color=theme.TRANSPARENT)
        footer.pack(side="bottom", fill="x", padx=theme.SPACE_LG, pady=theme.SPACE_MD)
        _divider(self).pack(side="bottom", fill="x", padx=1)

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

    # ------------------------------------------------------------------

    def update_counts(self, counts: list[tuple[str, int]], with_cte: int, without_cte: int) -> None:
        """counts: (CT-e, invoices) already sorted, most invoices first."""
        self._counts = counts
        self._distinct.configure(text=_plural(len(counts), "distinto", "distintos"))
        self._with_cte.configure(text=f"{with_cte:,}".replace(",", "."))
        self._without_cte.configure(text=f"{without_cte:,}".replace(",", "."))
        self._render()

    def select(self, cte: str | None) -> None:
        self._selected = cte
        self._render()

    def _render(self) -> None:
        counts = self._counts
        shown = counts[:MAX_ITEMS]
        largest = shown[0][1] if shown else 1

        while len(self._items) < len(shown):
            self._items.append(_CteItem(self._list, self._click))
        for index, item in enumerate(self._items):
            if index < len(shown):
                cte, count = shown[index]
                item.update_item(cte, count, largest, cte == self._selected)
                if not item.winfo_manager():
                    item.pack(fill="x", pady=(0, theme.SPACE_XS), before=self._more if self._more.winfo_manager() else None)
            elif item.winfo_manager():
                item.pack_forget()

        hidden = len(counts) - len(shown)
        if hidden > 0:
            self._more.configure(text=f"e mais {_plural(hidden, 'CT-e', 'CT-es')}")
            self._more.pack(pady=theme.SPACE_SM)
        else:
            self._more.pack_forget()
        if counts:
            self._empty.pack_forget()
        else:
            self._empty.pack(pady=theme.SPACE_XL)

    def _click(self, cte: str) -> None:
        self._on_pick_cte(None if cte == self._selected else cte)
