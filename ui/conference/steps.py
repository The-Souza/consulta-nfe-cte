import functools
import tkinter
import tkinter.font
from typing import Literal

import customtkinter as ctk
from PIL import Image, ImageDraw, ImageTk

from ui import theme
from ui.icons import ICONS_DIR, tint

STEPS = ("Carregar fotos", "Conferir NF-e e data", "Enviar")
_CIRCLE = 20
_CHECK = 12
_INSET = 5  # space between the circle and the pill border, as in the design
_SUPERSAMPLE = 4
# Height of a digit as a share of the font size (Roboto's cap height): Tk centers text by the whole line,
# descent included, which leaves a digit a little high in the circle.
_DIGIT_HEIGHT = 0.71

State = Literal["done", "active", "todo"]

# (pill background, pill border, label color, circle color, number color)
_LOOK: dict[State, tuple[str, str, str, str, str]] = {
    "done": (theme.STATUS["ok"][1], theme.STATUS["ok"][1], theme.STATUS["ok"][0], theme.PROGRESS,
             theme.STEP_DONE_MARK),
    "active": (theme.SURFACE_2, theme.STATUS["ok"][0], theme.TEXT, theme.TEXT, theme.BG),
    "todo": (theme.BG, theme.BORDER, theme.TEXT_MUTED, theme.STATUS["neutral"][1], theme.TEXT_MUTED),
}


@functools.lru_cache(maxsize=None)
def _circle(color: str, size: int) -> Image.Image:
    """A smooth filled circle: drawn large and scaled down (Tk canvas ovals have jagged edges)."""
    big = size * _SUPERSAMPLE
    image = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    ImageDraw.Draw(image).ellipse((0, 0, big - 1, big - 1), fill=color)
    return image.resize((size, size), Image.Resampling.LANCZOS)


@functools.lru_cache(maxsize=None)
def _check(color: str, size: int) -> Image.Image:
    with Image.open(ICONS_DIR / "check.png") as icon:
        return tint(icon, color).resize((size, size), Image.Resampling.LANCZOS)


class _Mark(tkinter.Canvas):
    """The circle of a step: its number, or a check once the step is done.

    CTk widgets pad themselves by their corner radius and stretch into a pill, and a label placed inside a
    frame sits off center: a canvas draws the circle and its content from the same center.
    """

    def __init__(self, parent, number: int, font: tkinter.font.Font, font_px: int, scaling: float):
        self._size = round(_CIRCLE * scaling)
        self._check_size = round(_CHECK * scaling)
        super().__init__(parent, width=self._size, height=self._size, highlightthickness=0, bd=0)
        # The middle pixel of the circle image, which is drawn from (0, 0); the number is centered on it too.
        center = (self._size - 1) // 2
        # Placed by the corner: with an odd size, a centered image lands half a pixel off and Tk cuts its last
        # row and column.
        self._circle = self.create_image(0, 0, anchor="nw")
        offset = (self._size - self._check_size) // 2
        self._mark = self.create_image(offset, offset, anchor="nw")
        # Anchored at the baseline: a digit fills the rows just above it, so its own middle goes to the
        # circle's middle.
        digit_px = round(_DIGIT_HEIGHT * font_px)
        baseline = center + (digit_px + 1) // 2
        self._number = self.create_text(center, baseline + font.metrics("descent"), text=str(number),
                                         font=font, anchor="s")
        self._photos: list[ImageTk.PhotoImage] = []  # Tk shows a PhotoImage only while Python holds it

    def paint(self, state: State) -> None:
        background, _, _, circle, number = _LOOK[state]
        self.configure(bg=background)
        self._photos = [ImageTk.PhotoImage(_circle(circle, self._size), master=self)]
        self.itemconfigure(self._circle, image=self._photos[0])
        if state == "done":
            self._photos.append(ImageTk.PhotoImage(_check(number, self._check_size), master=self))
            self.itemconfigure(self._mark, image=self._photos[1], state="normal")
            self.itemconfigure(self._number, state="hidden")
        else:
            self.itemconfigure(self._mark, state="hidden")
            self.itemconfigure(self._number, fill=number, state="normal")


class Steps(ctk.CTkFrame):
    """The "1 Carregar fotos · 2 Conferir NF-e e data · 3 Enviar" header: the steps before the current one
    are done (green, with a check), as in the design."""

    def __init__(self, parent):
        super().__init__(parent, fg_color=theme.TRANSPARENT)
        scaling = ctk.ScalingTracker.get_widget_scaling(self)  # plain Tk widgets are not scaled by CTk
        font_px = round(theme.FONT_SIZE_SM * scaling)
        # Kept on the instance: a collected Font deletes the named Tk font and the canvas text falls back.
        self._font = tkinter.font.Font(family=theme.FONT_FAMILY, size=-font_px, weight="bold")
        self._pills: list[tuple[ctk.CTkFrame, _Mark, ctk.CTkLabel]] = []
        self._lines: list[ctk.CTkFrame] = []
        for number, text in enumerate(STEPS, start=1):
            if number > 1:
                line = ctk.CTkFrame(self, width=28, height=2, corner_radius=0)
                line.pack(side="left", padx=theme.SPACE_MD)
                self._lines.append(line)
            pill = ctk.CTkFrame(self, height=30, corner_radius=15, border_width=1)
            pill.pack(side="left")
            mark = _Mark(pill, number, self._font, font_px, scaling)
            # Unlike CTk widgets, a Tk canvas's pack() does not scale its padding by the Windows zoom. CTk draws
            # the pill's bottom border one pixel inside the frame, so one more pixel below keeps the circle
            # centered between the two lines (measured on screenshots at 125%).
            inset = round(_INSET * scaling)
            mark.pack(side="left", padx=(inset, round(theme.SPACE_SM * scaling)), pady=(inset, inset + 1))
            label = ctk.CTkLabel(pill, text=text, height=20, font=theme.font(theme.FONT_SIZE_BODY, "bold"))
            label.pack(side="left", padx=(0, theme.SPACE_MD))
            self._pills.append((pill, mark, label))

    def set_active(self, step: int) -> None:
        for number, (pill, mark, label) in enumerate(self._pills, start=1):
            state: State = "done" if number < step else "active" if number == step else "todo"
            background, border, text, _, _ = _LOOK[state]
            pill.configure(fg_color=background, border_color=border)
            mark.paint(state)
            label.configure(text_color=text)
        # The line after a done step is green too
        for number, line in enumerate(self._lines, start=1):
            line.configure(fg_color=theme.SELECTED_BORDER if number < step else theme.BORDER)
