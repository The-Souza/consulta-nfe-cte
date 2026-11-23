from typing import Callable

import customtkinter as ctk

from ui import theme
from ui.icons import get_icon
from ui.titlebar import round_corners
from ui.widgets.scrollbar import use_theme_width

_ROW = 30
_MAX_ROWS = 8  # more options scroll
_GAP = 4  # between the field and the list


class Select(ctk.CTkFrame):
    """A select drawn by the app. CTkOptionMenu opens the native Windows menu, which Tk can't style: it comes
    with a thick white frame and a width set by the longest option. This list matches the field's width and the
    theme, highlights the current value and scrolls when there are many options."""

    def __init__(self, parent, placeholder: str, command: Callable[[str], None], height: int = 34):
        super().__init__(parent, fg_color=theme.INPUT_BG, border_width=1, border_color=theme.BORDER_INPUT,
                         corner_radius=theme.RADIUS_INPUT, height=height)
        self._command = command
        self._values: list[str] = []
        self._value = placeholder
        self._popover: ctk.CTkToplevel | None = None
        self._font = theme.font(theme.FONT_SIZE_BODY)

        self._label = ctk.CTkLabel(self, text=placeholder, anchor="w", height=height - 8, text_color=theme.TEXT,
                                   font=self._font)
        self._arrow = ctk.CTkLabel(self, text="", width=16, height=height - 8,
                                   image=get_icon("chevron-down", 16, theme.TEXT_MUTED))
        self._arrow.pack(side="right", padx=(0, 10), pady=3)
        self._label.pack(side="left", fill="x", expand=True, padx=(10, 4), pady=3)
        for widget in (self, self._label, self._arrow):
            widget.configure(cursor="hand2")
            widget.bind("<Button-1>", self._toggle)
            widget.bind("<Enter>", lambda _e: self.configure(border_color=theme.TEXT_MUTED))
            widget.bind("<Leave>", lambda _e: self._popover or self.configure(border_color=theme.BORDER_INPUT))
        # A click anywhere else in the window closes the list. Bound on the window, which sees the clicks of all
        # its widgets; the list is a window of its own, so clicks on its options don't reach this.
        window = self.winfo_toplevel()
        window.bind("<Button-1>", self._on_window_click, add="+")
        window.bind("<Escape>", lambda _e: self._close(), add="+")

    def get(self) -> str:
        return self._value

    def set(self, value: str) -> None:
        self._value = value
        self._label.configure(text=value)

    def set_values(self, values: list[str]) -> None:
        self._values = list(values)

    def destroy(self) -> None:
        self._close()
        super().destroy()

    # ------------------------------------------------------------------

    def _toggle(self, _event=None) -> None:
        if self._popover is not None:
            self._close()
        elif self._values:
            self._open()

    def _on_window_click(self, event) -> None:
        if self._popover is not None and not str(event.widget).startswith(str(self)):
            self._close()

    def _open(self) -> None:
        scaling = ctk.ScalingTracker.get_window_scaling(self)
        rows = min(len(self._values), _MAX_ROWS)
        width = round(self.winfo_width() / scaling)  # CTkToplevel.geometry scales the size, not the position
        height = rows * _ROW + 10

        top = ctk.CTkToplevel(self, fg_color=theme.BORDER_INPUT)
        top.withdraw()
        top.overrideredirect(True)
        top.transient(self.winfo_toplevel())
        scrolls = len(self._values) > _MAX_ROWS
        if scrolls:
            body = ctk.CTkScrollableFrame(
                top, fg_color=theme.SURFACE, corner_radius=0, scrollbar_button_color=theme.SCROLLBAR_BUTTON,
                scrollbar_button_hover_color=theme.SCROLLBAR_BUTTON_HOVER,
            )
            use_theme_width(body)
        else:
            body = ctk.CTkFrame(top, fg_color=theme.SURFACE, corner_radius=0)
        body.pack(fill="both", expand=True, padx=1, pady=1)
        for value in self._values:
            current = value == self._value
            ctk.CTkButton(
                body, text=value, anchor="w", height=_ROW, corner_radius=theme.RADIUS_INPUT - 2,
                fg_color=theme.SURFACE_2 if current else theme.TRANSPARENT, hover_color=theme.SURFACE_2,
                text_color=theme.TEXT, font=theme.font(theme.FONT_SIZE_BODY, "bold" if current else "normal"),
                command=lambda v=value: self._pick(v),
            ).pack(fill="x", padx=4, pady=(4 if value == self._values[0] else 0, 0))

        x = self.winfo_rootx()
        y = self.winfo_rooty() + self.winfo_height() + _GAP
        if y + height * scaling > self.winfo_screenheight():  # no room below: open above the field
            y = self.winfo_rooty() - _GAP - round(height * scaling)
        top.geometry(f"{width}x{height}+{x}+{y}")
        top.deiconify()
        round_corners(top)
        top.lift()
        top.bind("<Escape>", lambda _e: self._close())
        self._popover = top
        self.configure(border_color=theme.TEXT_MUTED)

    def _pick(self, value: str) -> None:
        self._close()
        self.set(value)
        self._command(value)

    def _close(self) -> None:
        if self._popover is not None:
            self._popover.destroy()
            self._popover = None
        if self.winfo_exists():
            self.configure(border_color=theme.BORDER_INPUT)
