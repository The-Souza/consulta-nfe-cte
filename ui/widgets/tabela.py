import customtkinter as ctk


def fazer_cabecalho(parent, cols: list[tuple[str, int]]) -> ctk.CTkFrame:
    f = ctk.CTkFrame(parent, height=36)
    f.pack_propagate(False)
    ctk.CTkFrame(f, width=8, fg_color="transparent").pack(side="left")
    for txt, w in cols:
        cell = ctk.CTkFrame(f, width=w, fg_color="transparent")
        cell.pack(side="left")
        cell.pack_propagate(False)
        ctk.CTkLabel(cell, text=txt, font=ctk.CTkFont(weight="bold"), anchor="center").pack(fill="both", expand=True)
    return f


def inserir_linha(
    parent,
    row_num: int,
    cols: list[tuple[str, int]],
    textos: list[str],
    status: str,
    cor_fg: str | None,
    cor_bg: str | None,
) -> None:
    row_bg = "#252525" if row_num % 2 == 0 else "transparent"
    mono = ctk.CTkFont(family="Consolas", size=12)
    linha = ctk.CTkFrame(parent, height=30, fg_color=row_bg)
    linha.pack(fill="x")
    linha.pack_propagate(False)

    for (_, w), txt in zip(cols[:-1], textos):
        cell = ctk.CTkFrame(linha, width=w, height=30, fg_color="transparent")
        cell.pack(side="left")
        cell.pack_propagate(False)
        ctk.CTkLabel(cell, text=txt, anchor="center", font=mono).pack(fill="both", expand=True)

    _, status_w = cols[-1]
    cell = ctk.CTkFrame(linha, width=status_w, height=30, fg_color="transparent")
    cell.pack(side="left")
    cell.pack_propagate(False)
    if cor_fg:
        badge = ctk.CTkFrame(cell, fg_color=cor_bg, corner_radius=9, height=18)
        badge.place(relx=0.5, rely=0.5, anchor="center")
        ctk.CTkLabel(badge, text=status, text_color=cor_fg,
                     font=ctk.CTkFont(size=10), height=16).pack(side="left", padx=8, pady=0)
    else:
        ctk.CTkLabel(cell, text=status, anchor="center").pack(fill="both", expand=True)


def limpar_scroll(scroll: ctk.CTkScrollableFrame) -> None:
    for w in scroll.winfo_children():
        w.destroy()
    scroll._parent_canvas.yview_moveto(0)
