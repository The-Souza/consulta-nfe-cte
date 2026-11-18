import customtkinter as ctk

from ui import theme
from utils.status import Tone


def make_header(parent, cols: list[tuple[str, int]]) -> ctk.CTkFrame:
    f = ctk.CTkFrame(parent, height=36, fg_color=theme.SURFACE)
    f.pack_propagate(False)
    ctk.CTkFrame(f, width=8, fg_color=theme.TRANSPARENT).pack(side="left")
    for txt, w in cols:
        cell = ctk.CTkFrame(f, width=w, fg_color=theme.TRANSPARENT)
        cell.pack(side="left")
        cell.pack_propagate(False)
        ctk.CTkLabel(
            cell, text=txt, text_color=theme.TEXT_LABEL, font=theme.font(theme.FONT_SIZE_SM, "bold"), anchor="center",
        ).pack(fill="both", expand=True)
    return f


def insert_row(
    parent,
    row_num: int,
    cols: list[tuple[str, int]],
    texts: list[str],
    status_text: str,
    tone: Tone,
) -> ctk.CTkFrame:
    row_bg = theme.SURFACE_2 if row_num % 2 == 0 else theme.TRANSPARENT
    mono = theme.font(theme.FONT_SIZE_SM, mono=True)
    row = ctk.CTkFrame(parent, height=30, fg_color=row_bg, corner_radius=0)
    row.pack(fill="x")
    row.pack_propagate(False)

    for (_, w), txt in zip(cols[:-1], texts):
        cell = ctk.CTkFrame(row, width=w, height=30, fg_color=theme.TRANSPARENT)
        cell.pack(side="left")
        cell.pack_propagate(False)
        ctk.CTkLabel(cell, text=txt, text_color=theme.TEXT, anchor="center", font=mono).pack(fill="both", expand=True)

    _, status_w = cols[-1]
    cell = ctk.CTkFrame(row, width=status_w, height=30, fg_color=theme.TRANSPARENT)
    cell.pack(side="left")
    cell.pack_propagate(False)
    text_color, bg_color = theme.STATUS[tone.value]
    badge = ctk.CTkFrame(cell, fg_color=bg_color, corner_radius=theme.RADIUS_CHIP, height=18)
    badge.place(relx=0.5, rely=0.5, anchor="center")
    ctk.CTkLabel(
        badge, text=status_text, text_color=text_color, font=theme.font(theme.FONT_SIZE_XS), height=16,
    ).pack(side="left", padx=theme.SPACE_SM, pady=0)
    return row


def clear_scroll(scroll: ctk.CTkScrollableFrame) -> None:
    for w in scroll.winfo_children():
        w.destroy()
    scroll._parent_canvas.yview_moveto(0)
