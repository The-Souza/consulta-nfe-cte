"""CTkScrollbar always draws its handle, filling the whole track when there is nothing to scroll.
These helpers paint the handle with the background in that case, keeping the track's space so the
content beside it doesn't change width when the handle shows up."""
from typing import Callable

import customtkinter as ctk

from ui import theme


def needs_scroll(first: str | float, last: str | float) -> bool:
    return float(first) > 0 or float(last) < 1


def hide_when_idle(
    scrollbar: ctk.CTkScrollbar,
    button_color: str = theme.SCROLLBAR_BUTTON,
    hover_color: str = theme.SCROLLBAR_BUTTON_HOVER,
) -> Callable[[str, str], None]:
    """A yscrollcommand for the scrolled widget. The colors change only when the state flips,
    because configure() redraws the whole scrollbar."""
    shown: bool | None = None

    def command(first: str, last: str) -> None:
        nonlocal shown
        scrollbar.set(first, last)
        # set() redraws and processes pending Tk events, which can call this command again with a
        # newer position: decide by the position the scrollbar ended up with, not by these arguments.
        show = needs_scroll(*scrollbar.get())
        if show == shown:
            return
        shown = show
        if show:
            scrollbar.configure(button_color=button_color, button_hover_color=hover_color)
        else:
            background = scrollbar.cget("bg_color")
            scrollbar.configure(button_color=background, button_hover_color=background)

    return command


def use_theme_width(frame: ctk.CTkScrollableFrame) -> None:
    """CTkScrollableFrame has no width option for its scrollbar (default 16): match the results table's."""
    frame._scrollbar.configure(width=theme.SCROLLBAR_WIDTH)


def hide_frame_scrollbar_when_idle(frame: ctk.CTkScrollableFrame) -> None:
    # CTkScrollableFrame has no public hook for its scrollbar: rewire the canvas it scrolls
    bar = frame._scrollbar
    # cget names the button colors "scrollbar_color", while configure takes "button_color"
    command = hide_when_idle(bar, bar.cget("scrollbar_color"), bar.cget("scrollbar_hover_color"))
    frame._parent_canvas.configure(yscrollcommand=command)
