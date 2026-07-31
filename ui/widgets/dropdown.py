import tkinter
from typing import Callable

import customtkinter as ctk


class FilterDropdown:
    """Select-style dropdown (label + arrow) with a custom-drawn popup list.

    Windows always paints a system-colored (white) border around Tk's native
    Menu popup, which can't be recolored via CTkOptionMenu. This draws the
    popup itself as a borderless CTkToplevel styled with CTk widgets, so the
    border stays themeable. The popup opens right-aligned to the trigger so
    it doesn't spill off-screen when the trigger sits near the window edge.
    """

    def __init__(self, parent, options: list[str], command: Callable[[str], None], width: int = 160):
        self._options      = options
        self._command      = command
        self._value        = options[0]
        self._popup: tkinter.Toplevel | None = None
        self._just_closed  = False

        self._frame = ctk.CTkFrame(
            parent, width=width, height=28, corner_radius=6,
            border_width=1, border_color="gray", cursor="hand2",
        )
        self._frame.pack_propagate(False)

        self._label = ctk.CTkLabel(self._frame, text=self._value, anchor="w")
        self._label.pack(side="left", fill="both", expand=True, padx=(10, 0), pady=4)

        self._arrow = ctk.CTkLabel(self._frame, text="▾", width=24)
        self._arrow.pack(side="right", fill="y", padx=(0, 4), pady=4)

        for widget in (self._frame, self._label, self._arrow):
            widget.bind("<Button-1>", lambda e: self._toggle())

    def pack(self, **kwargs) -> None:
        self._frame.pack(**kwargs)

    def get(self) -> str:
        return self._value

    def set(self, value: str) -> None:
        self._value = value
        self._label.configure(text=value)

    def _toggle(self) -> None:
        if self._popup is not None:
            self._close()
        elif not self._just_closed:
            self._open()

    def _open(self) -> None:
        row_height = 26
        longest = max(len(opt) for opt in self._options)
        popup_width = max(self._frame.winfo_width(), longest * 8 + 32)

        btn_right = self._frame.winfo_rootx() + self._frame.winfo_width()
        x = max(btn_right - popup_width, 0)
        y = self._frame.winfo_rooty() + self._frame.winfo_height() + 2

        # A plain tkinter.Toplevel is used instead of CTkToplevel: CTkToplevel
        # rescales geometry() strings for DPI, which would throw off the
        # pixel-accurate right-alignment computed above.
        popup = tkinter.Toplevel(self._frame)
        popup.configure(bg="#252525")
        popup.overrideredirect(True)
        popup.attributes("-topmost", True)
        popup.geometry(f"{popup_width}x{row_height * len(self._options) + 4}+{x}+{y}")

        frame = ctk.CTkFrame(popup, fg_color="#252525", border_width=1, border_color="#3a3a3a", corner_radius=6)
        frame.pack(fill="both", expand=True)
        for opt in self._options:
            ctk.CTkButton(
                frame, text=opt, height=row_height - 2, corner_radius=0,
                anchor="w", fg_color="transparent", hover_color="#3a3a3a",
                text_color="#e0e0e0",
                command=lambda o=opt: self._select(o),
            ).pack(fill="x", padx=2, pady=1)

        popup.bind("<FocusOut>", lambda e: self._close())
        popup.bind("<Escape>", lambda e: self._close())
        popup.focus_force()
        self._popup = popup

    def _select(self, value: str) -> None:
        self.set(value)
        self._close()
        self._command(value)

    def _close(self) -> None:
        if self._popup is not None:
            self._popup.destroy()
            self._popup = None
            self._just_closed = True
            self._frame.after(200, self._reset_just_closed)

    def _reset_just_closed(self) -> None:
        self._just_closed = False
