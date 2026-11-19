import tkinter.font
from tkinter import ttk

import customtkinter as ctk

from ui import theme
from utils.status import Tone, search_tone

_STYLE = "Canhotos.Treeview"
_DASH = "—"

# (id, heading, width, anchor, stretch)
_COLUMNS = [
    ("n",        "Nº",        56,  "center", False),
    ("nfe",      "NF-E",      104, "w",      False),
    ("cte",      "CT-E",      124, "w",      False),
    ("image",    "IMAGEM",    84,  "w",      False),
    ("driver",   "MOTORISTA", 180, "w",      True),
    ("delivery", "ENTREGA",   92,  "w",      False),
    ("status",   "STATUS",    190, "w",      False),
]


def _scaled(widget, value: float) -> int:
    # ttk is not scaled by CustomTkinter: apply the Windows zoom by hand.
    return round(value * ctk.ScalingTracker.get_widget_scaling(widget))


def _configure_style(widget) -> tuple[tkinter.font.Font, ...]:
    """Returns the fonts it created: the caller must keep them, or Python collects them, Tk deletes the
    named fonts and the Treeview falls back to the default font."""
    style = ttk.Style(widget)
    style.theme_use("clam")  # the only built-in theme that honors these colors on Windows
    body = tkinter.font.Font(family=theme.FONT_FAMILY, size=-_scaled(widget, theme.FONT_SIZE_BODY))
    heading = tkinter.font.Font(
        family=theme.FONT_FAMILY, size=-_scaled(widget, theme.FONT_SIZE_XS), weight="bold",
    )
    style.layout(_STYLE, [(f"{_STYLE}.treearea", {"sticky": "nswe"})])  # no border
    style.configure(
        _STYLE, background=theme.SURFACE, fieldbackground=theme.SURFACE, foreground=theme.TEXT,
        rowheight=_scaled(widget, 34), borderwidth=0, font=body,
    )
    style.map(_STYLE, background=[("selected", theme.SURFACE_2)], foreground=[("selected", theme.TEXT)])
    style.configure(
        f"{_STYLE}.Heading", background=theme.SURFACE, foreground=theme.TEXT_MUTED, relief="flat",
        borderwidth=0, font=heading, padding=(_scaled(widget, 8), _scaled(widget, 10)),
    )
    style.map(f"{_STYLE}.Heading", background=[("active", theme.SURFACE)])
    return body, heading


def _image_text(value) -> str:
    return value if value in ("Sim", "Não") else _DASH


def _cte_text(cte: str, multiplicity: dict[str, int]) -> str:
    if cte in ("-", ""):
        return _DASH
    count = multiplicity.get(cte, 1)
    return f"{cte}  ×{count}" if count > 1 else cte


class ResultsTable(ctk.CTkFrame):
    """Search results in a ttk.Treeview: fast with hundreds of rows, and a row can be updated in
    place (its iid is the NF-e). The whole row is drawn in the status color, except OK rows."""

    def __init__(self, parent):
        super().__init__(parent, fg_color=theme.SURFACE, corner_radius=0)
        self._fonts = _configure_style(self)

        self._tree = ttk.Treeview(
            self, columns=[c[0] for c in _COLUMNS], show="headings", style=_STYLE, selectmode="browse",
        )
        for col, heading, width, anchor, stretch in _COLUMNS:
            self._tree.heading(col, text=heading, anchor=anchor)
            self._tree.column(col, width=_scaled(self, width), minwidth=_scaled(self, 40), anchor=anchor,
                              stretch=stretch)
        self._tree.tag_configure("odd", background=theme.SURFACE_2)
        for tone in Tone:
            if tone is not Tone.OK:
                self._tree.tag_configure(tone.value, foreground=theme.STATUS[tone.value][0])

        scrollbar = ctk.CTkScrollbar(
            self, command=self._tree.yview, width=theme.SCROLLBAR_WIDTH, fg_color=theme.TRANSPARENT,
            button_color=theme.SCROLLBAR_BUTTON, button_hover_color=theme.SCROLLBAR_BUTTON_HOVER,
        )
        self._tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y", padx=(0, 2), pady=2)
        self._tree.pack(side="left", fill="both", expand=True)

        self._empty = ctk.CTkLabel(
            self, text="", text_color=theme.TEXT_MUTED, fg_color=theme.SURFACE, font=theme.font(theme.FONT_SIZE_INPUT),
        )

    # ------------------------------------------------------------------

    def _values(self, number: int, row: dict, multiplicity: dict[str, int]) -> tuple:
        return (
            number, row["NF-e"], _cte_text(row["CT-e"], multiplicity), _image_text(row.get("Imagem")),
            _DASH, _DASH, row["Status"],
        )

    @staticmethod
    def _tags(index: int, row: dict) -> tuple[str, ...]:
        tags = ["odd"] if index % 2 else []
        tone = search_tone(row["Status"])
        if tone is not Tone.OK:
            tags.append(tone.value)
        return tuple(tags)

    def show(self, rows: list[dict], multiplicity: dict[str, int], empty_text: str = "") -> None:
        """Replace the table with `rows`. `empty_text` is shown when there is no row."""
        self._tree.delete(*self._tree.get_children())
        for index, row in enumerate(rows):
            self._insert(index, row, multiplicity)
        self._toggle_empty(empty_text)
        self._tree.yview_moveto(0)

    def append(self, row: dict, multiplicity: dict[str, int]) -> None:
        self._insert(len(self._tree.get_children()), row, multiplicity)
        self._toggle_empty("")

    def update_row(self, row: dict, multiplicity: dict[str, int]) -> bool:
        """Update a row on screen in place. False when the row is not shown (filtered out)."""
        iid = str(row["NF-e"])
        if not self._tree.exists(iid):
            return False
        index = self._tree.index(iid)
        self._tree.item(iid, values=self._values(index + 1, row, multiplicity), tags=self._tags(index, row))
        return True

    def refresh_multiplicity(self, multiplicity: dict[str, int], rows: dict[int, dict]) -> None:
        """Rewrite only the CT-e column, after a new row changed how many share a CT-e."""
        for iid in self._tree.get_children():
            self._tree.set(iid, "cte", _cte_text(rows[int(iid)]["CT-e"], multiplicity))

    def clear(self) -> None:
        self.show([], {}, "")

    def _insert(self, index: int, row: dict, multiplicity: dict[str, int]) -> None:
        self._tree.insert(
            "", "end", iid=str(row["NF-e"]), values=self._values(index + 1, row, multiplicity),
            tags=self._tags(index, row),
        )

    def _toggle_empty(self, empty_text: str) -> None:
        if empty_text and not self._tree.get_children():
            self._empty.configure(text=empty_text)
            self._empty.place(relx=0.5, rely=0.35, anchor="center")
        else:
            self._empty.place_forget()
