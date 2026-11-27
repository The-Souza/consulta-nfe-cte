import tkinter
from tkinter import ttk
from typing import Callable

import customtkinter as ctk
from PIL import Image, ImageTk

from conference.labels import row_values, status_tone
from conference.photo import Photo, Status
from ui import theme
from ui.icons import ICONS_DIR, tint
from ui.widgets.results_table import STYLE, configure_style, scaled
from ui.widgets.scrollbar import hide_when_idle
from utils.status import Tone

# (id, heading, width, anchor, stretch)
_COLUMNS = [
    ("nfe",    "NF-E",    110, "w", False),
    ("file",   "ARQUIVO", 260, "w", True),
    ("date",   "DATA",    70,  "w", False),
    ("status", "STATUS",  110, "w", False),
]
_CHECK_COLUMN = 40  # the tree column: the selection box (R8), which also keeps the NF-e off the card edge
_CHECK_SIZE = 16
_HEADING_PAD_Y = 10
_HEADING_PAD_X = 2  # as configure_style sets it for the headings
_ITEM_STYLE = f"{STYLE}.Item"
# Only the rows that need attention (unread, duplicate) take their status color: every photo is "Sem data" until
# the portal is checked, and a whole list in yellow would hide them.
_HIGHLIGHT = {Tone.ERROR}


class PhotoList(ctk.CTkFrame):
    """The photos of the review in a ttk.Treeview (light with hundreds of rows); the iid is the file name.

    The tree column holds the selection box of each row; its heading checks or clears every row shown.
    """

    def __init__(self, parent, on_toggle: Callable[[str], None], on_toggle_all: Callable[[], None]):
        super().__init__(parent, fg_color=theme.SURFACE, corner_radius=0)
        self._on_toggle = on_toggle
        self._fonts = configure_style(self)
        size = scaled(self, _CHECK_SIZE)
        # ttk takes Tk images, which are not scaled by CTk; kept here or Tk shows nothing.
        self._boxes = {
            False: self._box("square", theme.TEXT_MUTED, size),
            True: self._box("square-check", theme.STATUS["ok"][0], size),
        }
        # The heading draws its image at the right of the column (where ttk puts the sort arrow), whatever the
        # anchor: the box of each row goes there too, with the heading's padding, and no expand-arrow space.
        style = ttk.Style(self)
        style.layout(_ITEM_STYLE, [
            ("Treeitem.padding", {"sticky": "nswe", "children": [("Treeitem.image", {"side": "right", "sticky": ""})]}),
        ])
        style.configure(_ITEM_STYLE, padding=(0, 0, scaled(self, _HEADING_PAD_X), 0))
        self._tree = ttk.Treeview(
            self, columns=[c[0] for c in _COLUMNS], show="tree headings", style=STYLE, selectmode="none",
            takefocus=False,
        )
        self._tree.column("#0", width=scaled(self, _CHECK_COLUMN), minwidth=scaled(self, _CHECK_COLUMN),
                          stretch=False, anchor="center")
        self._tree.heading("#0", image=self._boxes[False], command=on_toggle_all)
        for col, heading, width, anchor, stretch in _COLUMNS:
            self._tree.heading(col, text=heading, anchor=anchor)
            self._tree.column(col, width=scaled(self, width), minwidth=scaled(self, 40), anchor=anchor,
                              stretch=stretch)
        self._tree.tag_configure("odd", background=theme.SURFACE_2)
        for tone in _HIGHLIGHT:
            self._tree.tag_configure(tone.value, foreground=theme.STATUS[tone.value][0])
        self._tree.bind("<Button-1>", self._on_click)

        scrollbar = ctk.CTkScrollbar(
            self, command=self._tree.yview, width=theme.SCROLLBAR_WIDTH, fg_color=theme.TRANSPARENT,
            button_color=theme.SCROLLBAR_BUTTON, button_hover_color=theme.SCROLLBAR_BUTTON_HOVER,
        )
        self._tree.configure(yscrollcommand=hide_when_idle(scrollbar))
        heading_height = self._fonts[1].metrics("linespace") + 2 * scaled(self, _HEADING_PAD_Y)
        # As in the search table: the scrollbar starts below the headings, and pack() scales its pady again.
        scaling = ctk.ScalingTracker.get_widget_scaling(self)
        scrollbar.pack(side="right", fill="y", padx=(0, 2), pady=((heading_height + 1) / scaling, 2))
        self._tree.pack(side="left", fill="both", expand=True)
        tkinter.Frame(self, height=1, bg=theme.BORDER, bd=0, highlightthickness=0).place(
            x=0, y=heading_height, relwidth=1,
        )
        self._empty = ctk.CTkLabel(
            self, text="", text_color=theme.TEXT_MUTED, fg_color=theme.SURFACE, font=theme.font(theme.FONT_SIZE_INPUT),
        )

    def _box(self, icon: str, color: str, size: int) -> ImageTk.PhotoImage:
        with Image.open(ICONS_DIR / f"{icon}.png") as image:
            return ImageTk.PhotoImage(tint(image, color).resize((size, size), Image.Resampling.LANCZOS), master=self)

    def _on_click(self, event) -> str | None:
        """A click on a row's box checks or clears it; the rest of the row is for opening the photo (6d)."""
        if self._tree.identify_region(event.x, event.y) != "tree" or self._tree.identify_column(event.x) != "#0":
            return None
        row = self._tree.identify_row(event.y)
        if row:
            self._on_toggle(row)
        return "break"

    def show(self, rows: list[tuple[Photo, Status]], empty_text: str, checked: set[str]) -> None:
        """Replaces the rows, keeping the scroll position (the list is redrawn while photos arrive)."""
        top = self._tree.yview()[0]
        self._tree.delete(*self._tree.get_children())
        for index, (photo, status) in enumerate(rows):
            tags = ["odd"] if index % 2 else []
            tone = status_tone(status)
            if tone in _HIGHLIGHT:
                tags.append(tone.value)
            self._tree.insert("", "end", iid=photo.name, image=self._boxes[photo.name in checked],
                              values=row_values(photo, status), tags=tuple(tags))
        self._tree.yview_moveto(top)
        self._tree.heading("#0", image=self._boxes[bool(rows) and all(p.name in checked for p, _ in rows)])
        if rows:
            self._empty.place_forget()
        else:
            self._empty.configure(text=empty_text)
            self._empty.place(relx=0.5, rely=0.35, anchor="center")
