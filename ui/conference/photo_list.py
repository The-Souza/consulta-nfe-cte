import tkinter
from tkinter import ttk

import customtkinter as ctk

from conference.labels import row_values, status_tone
from conference.photo import Photo, Status
from ui import theme
from ui.widgets.results_table import STYLE, configure_style, scaled
from ui.widgets.scrollbar import hide_when_idle
from utils.status import Tone

# (id, heading, width, anchor, stretch)
# The cells have no padding: an empty first column keeps the NF-e off the card edge, and the stripes still
# reach it.
_COLUMNS = [
    ("pad",    "",        12,  "w", False),
    ("nfe",    "NF-E",    110, "w", False),
    ("file",   "ARQUIVO", 260, "w", True),
    ("date",   "DATA",    70,  "w", False),
    ("status", "STATUS",  110, "w", False),
]
_HEADING_PAD_Y = 10
# Only the rows that need attention (unread, duplicate) take their status color: every photo is "Sem data" until
# the portal is checked, and a whole list in yellow would hide them.
_HIGHLIGHT = {Tone.ERROR}


class PhotoList(ctk.CTkFrame):
    """The photos of the review in a ttk.Treeview (light with hundreds of rows); the iid is the file name."""

    def __init__(self, parent):
        super().__init__(parent, fg_color=theme.SURFACE, corner_radius=0)
        self._fonts = configure_style(self)
        self._tree = ttk.Treeview(
            self, columns=[c[0] for c in _COLUMNS], show="headings", style=STYLE, selectmode="none",
            takefocus=False,
        )
        for col, heading, width, anchor, stretch in _COLUMNS:
            self._tree.heading(col, text=heading, anchor=anchor)
            self._tree.column(col, width=scaled(self, width), minwidth=scaled(self, min(width, 40)), anchor=anchor,
                              stretch=stretch)
        self._tree.tag_configure("odd", background=theme.SURFACE_2)
        for tone in _HIGHLIGHT:
            self._tree.tag_configure(tone.value, foreground=theme.STATUS[tone.value][0])

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

    def show(self, rows: list[tuple[Photo, Status]], empty_text: str) -> None:
        """Replaces the rows, keeping the scroll position (the list is redrawn while photos arrive)."""
        top = self._tree.yview()[0]
        self._tree.delete(*self._tree.get_children())
        for index, (photo, status) in enumerate(rows):
            tags = ["odd"] if index % 2 else []
            tone = status_tone(status)
            if tone in _HIGHLIGHT:
                tags.append(tone.value)
            self._tree.insert("", "end", iid=photo.name, values=("", *row_values(photo, status)), tags=tuple(tags))
        self._tree.yview_moveto(top)
        if rows:
            self._empty.place_forget()
        else:
            self._empty.configure(text=empty_text)
            self._empty.place(relx=0.5, rely=0.35, anchor="center")
